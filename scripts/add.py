#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add.py：投递 + 受理（§3.0）。退出码：0=受理成功 / 2=重复 / 1=错误。"""
import argparse
import os
import sys
import time

import schema
import taskqueue as queue
import registry
from identity import classify, identify


def build_parser():
    p = argparse.ArgumentParser(description="Submit a literature collection task and register it immediately")
    p.add_argument("source", nargs="?", help="URL / bare arXiv id / local path (PDF or .url)")
    p.add_argument("--inbox", metavar="NAME.pdf", help="supply metadata for a PDF already in _inbox")
    p.add_argument("--repo", action="append", default=[], help="owner/repo | URL | local path; repeatable")
    p.add_argument("--support", action="append", default=[], help="supplementary material URL; repeatable")
    p.add_argument("--doi", default=None, help="explicit DOI; overrides filename/URL identification and hash fallback")
    p.add_argument("--wait", action="store_true", help="block until done/rejected/duplicate")
    p.add_argument("--root", default=None, help="data root (env REFERENCE_WORKS as fallback)")
    return p


def submit(source_value=None, inbox_name=None, repo=None, support=None, root=None, doi=None):
    """受理核心（collect.py 复用）。返回 (code, task, paper_id, error_msg)。

    code: 0=受理成功(registered 或续跑) / 2=duplicate / 1=错误。
    """
    root = schema.ensure_root(schema.resolve_root(root))
    repo, support = repo or [], support or []

    if inbox_name:
        ibox = schema.inbox_dir(root)
        pdf = os.path.join(ibox, inbox_name)
        jpair = os.path.join(ibox, os.path.splitext(inbox_name)[0] + ".json")
        if not os.path.exists(pdf):
            return 1, None, None, f"{inbox_name} not found in _inbox"
        if os.path.exists(jpair):
            return 1, None, None, f"{inbox_name} already has a paired json; leave it to the worker"
        task_id = queue.new_task_id()
        moved = queue._claim(root, task_id, [pdf])
        source = {"type": "pdf_path", "value": moved[inbox_name]}
        task = queue.create_task(root, source, repo=repo, support=support,
                                 submitted_by={"kind": "human"}, task_id=task_id, doi=doi)
    else:
        if not source_value:
            return 1, None, None, "missing <source> (mutually exclusive with --inbox)"
        source = classify(source_value)
        task = queue.create_task(root, source, repo=repo, support=support,
                                 submitted_by={"kind": "human"}, doi=doi)

    # id 生成：本地文件可提前算内容哈希（强键）
    content_sha = None
    if source["type"] == "pdf_path" and os.path.isfile(source["value"]):
        content_sha = schema.sha256_file(source["value"])
    try:
        paper_id = identify(source, content_sha=content_sha, doi=doi)
    except ValueError as exc:
        return 1, task, None, str(exc)

    # 判重（唯一权威 processed.csv）
    rows = registry.load(root)
    repo_key = None
    if source["type"] == "repo_only":
        from identity import normalize_repo_url
        repo_key = normalize_repo_url(source["value"])
    hit, how = registry.find(rows, paper_id=paper_id, pdf_sha256=content_sha,
                             repo_url=repo_key)
    if hit:
        if hit.get("task_id") == task["task_id"]:
            pass  # 崩溃续跑：不新建
        else:
            queue.cleanup_input(root, task["task_id"])
            task["status"] = "duplicate"
            task["paper_id"] = hit["id"]
            queue.save_task(root, task)
            queue.log_event(root, "duplicate", task_id=task["task_id"], paper_id=hit["id"], by=how)
            return 2, task, hit["id"], None

    registry.register(root, task, paper_id,
                      source_str=f"{source['type']}:{source['value']}")
    task["paper_id"] = paper_id
    task["status"] = "queued"
    queue.save_task(root, task)
    queue.log_event(root, "registered", task_id=task["task_id"], paper_id=paper_id)
    return 0, task, paper_id, None


def wait_task(root, task_id, interval=5):
    while True:
        task = queue.load_task(schema.task_path(root, task_id))
        if task.get("status") in ("done", "rejected", "duplicate"):
            return task
        time.sleep(interval)


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.source and args.inbox:
        print("error: <source> and --inbox are mutually exclusive", file=sys.stderr)
        return 1
    root = schema.resolve_root(args.root)
    code, task, paper_id, err = submit(source_value=args.source, inbox_name=args.inbox,
                                       repo=args.repo, support=args.support, root=root, doi=args.doi)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return code
    if code == 2:
        print(f"duplicate {paper_id} (task {task['task_id']})")
        return 2
    print(f"task_id={task['task_id']} paper_id={paper_id} registered")
    if args.wait:
        final = wait_task(root, task["task_id"])
        print(f"final: {final['status']} paper_id={final.get('paper_id')}")
        return 0 if final["status"] == "done" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
