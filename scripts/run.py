#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run.py：worker——先 _inbox 后 _queue，FIFO，推进到 done（§3/§4）。

导出 run_once(root, until=None, from_stage=None, only_id=None) 供 collect.py / retry.py 编排。
"""
import argparse
import os
import sys

import schema
import taskqueue as queue
import registry
import fetch
import convert
import enrich
import catalog


def _rank(stage):
    if stage == schema.FAILED:
        return -1
    return schema.PIPELINE.index(stage) if stage in schema.PIPELINE else 0


def _next_stages(row, until=None, from_stage=None):
    """根据 csv 当前 stage 计算本趟要执行的阶段序列。"""
    cur = row.get("stage") or "registered"
    start = _rank(cur)
    if cur == schema.FAILED:
        # 失败续跑：从失败阶段重跑该阶段
        cur = row.get("error_stage") or "registered"
        start = _rank(cur) - 1
    if from_stage:
        start = _rank(from_stage) - 1
    end = _rank(until) if until else _rank("done")
    return [s for s in schema.PIPELINE if start < _rank(s) <= end]


def process_task(root, task, until=None, from_stage=None):
    """受理 + 驱动一条任务到终态。返回 (paper_id, final_stage)。"""
    rows = registry.load(root)
    paper_id = task.get("paper_id")
    row = rows.get(paper_id) if paper_id else None
    if row is None:
        # add 未受理（任务来自 _inbox 规范化）：此处受理
        import identity
        source = task["source"]
        content_sha = None
        if source["type"] == "pdf_path" and os.path.isfile(source["value"]):
            content_sha = schema.sha256_file(source["value"])
        paper_id = identity.identify(source, content_sha=content_sha, doi=task.get("doi"))
        hit, how = registry.find(rows, paper_id=paper_id, pdf_sha256=content_sha)
        if hit and hit.get("task_id") != task["task_id"]:
            queue.cleanup_input(root, task["task_id"])
            task["status"] = "duplicate"
            task["paper_id"] = hit["id"]
            queue.save_task(root, task)
            queue.log_event(root, "duplicate", task_id=task["task_id"], paper_id=hit["id"], by=how)
            return hit["id"], "duplicate"
        row = registry.register(root, task, paper_id,
                                source_str=f"{source['type']}:{source['value']}")
        task["paper_id"] = paper_id
    task["status"] = "running"
    queue.save_task(root, task)

    stages = _next_stages(row, until=until, from_stage=from_stage)
    final = row.get("stage")
    for stage in stages:
        try:
            if stage == "fetching":
                registry.set_stage(root, paper_id, "fetching", error="")
                info = fetch.fetch_paper(root, paper_id, task)
                # 下载完成后补 pdf sha256 复查一次判重（§3.0 第 4 条）
                pdf_sha = info["pdf"]["sha256"] if info.get("pdf") else None
                if pdf_sha:
                    hit, how = registry.find(registry.load(root), pdf_sha256=pdf_sha)
                    if hit and hit["id"] != paper_id:
                        import shutil
                        shutil.rmtree(schema.paper_dir(root, paper_id), ignore_errors=True)
                        rows = registry.load(root)
                        rows.pop(paper_id, None)
                        registry.save(root, rows)
                        task["status"] = "duplicate"
                        task["paper_id"] = hit["id"]
                        queue.save_task(root, task)
                        queue.log_event(root, "duplicate", task_id=task["task_id"],
                                        paper_id=hit["id"], by="pdf_sha256")
                        queue.cleanup_input(root, task["task_id"])
                        return hit["id"], "duplicate"
                registry.update(root, paper_id, pdf_sha256=pdf_sha or "")
                enrich.init_meta(root, paper_id, task, info)
                queue.cleanup_input(root, task["task_id"])
            elif stage == "converting":
                if task["source"]["type"] == "repo_only":
                    final = stage
                    continue  # 无 PDF，registered 后直接进 enriching
                registry.set_stage(root, paper_id, "converting")
                md = convert.convert(root, paper_id)
                registry.update(root, paper_id, md_sha256=schema.sha256_file(md))
            elif stage == "enriching":
                registry.set_stage(root, paper_id, "enriching")
                enrich.enrich(root, paper_id)
            elif stage == "cataloging":
                registry.set_stage(root, paper_id, "cataloging")
                catalog.write_catalog(root)
            elif stage == "done":
                pass
            final = stage
        except Exception as exc:
            registry.update(root, paper_id, stage=schema.FAILED,
                            error=str(exc), error_stage=stage)
            task["status"] = "rejected"
            queue.save_task(root, task)
            queue.log_event(root, "failed", task_id=task["task_id"],
                            paper_id=paper_id, stage=stage, error=str(exc))
            return paper_id, schema.FAILED
    registry.set_stage(root, paper_id, "done" if (not until or until == "done")
                       and _rank(final) >= _rank("cataloging") else final, error="")
    if registry.get(root, paper_id)["stage"] == "done":
        task["status"] = "done"
        queue.save_task(root, task)
        catalog.write_catalog(root)  # 刷新一次，使 catalog 中 stage 为终态
        queue.log_event(root, "done", task_id=task["task_id"], paper_id=paper_id)
    else:
        # --until 截断：任务保持 queued 供下趟续跑
        task["status"] = "queued"
        queue.save_task(root, task)
    return paper_id, registry.get(root, paper_id)["stage"]


def run_once(root, until=None, from_stage=None, only_id=None):
    """单次 worker 运行：扫 _inbox → 消费 _queue（FIFO）。返回 [(paper_id, stage)]。"""
    root = schema.ensure_root(schema.resolve_root(root))
    queue.scan_inbox(root)
    results = []
    for task in queue.list_tasks(root, status=["queued", "running"]):
        if only_id and task.get("paper_id") not in (None, only_id):
            continue
        results.append(process_task(root, task, until=until, from_stage=from_stage))
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="worker: scan _inbox/_queue and advance tasks to done")
    p.add_argument("--until", choices=schema.PIPELINE[1:], default=None)
    p.add_argument("--from", dest="from_stage", choices=schema.PIPELINE, default=None)
    p.add_argument("--root", default=None)
    args = p.parse_args(argv)
    results = run_once(args.root, until=args.until, from_stage=args.from_stage)
    for pid, stage in results:
        print(f"{pid}: {stage}")
    if not results:
        print("no pending tasks")
    return 0 if all(s != schema.FAILED for _, s in results) else 1


if __name__ == "__main__":
    sys.exit(main())
