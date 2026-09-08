#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retry.py：把 failed 行退回失败阶段重跑（§4）。"""
import argparse
import sys

import schema
import registry
import taskqueue as queue
import run


def main(argv=None):
    p = argparse.ArgumentParser(description="resume failed papers from the failed stage")
    p.add_argument("ids", nargs="*", help="retry only these ids (default: all failed)")
    p.add_argument("--root", default=None)
    args = p.parse_args(argv)
    root = schema.resolve_root(args.root)
    rows = registry.load(root)
    targets = [pid for pid, r in rows.items()
               if r.get("stage") == schema.FAILED and (not args.ids or pid in args.ids)]
    if not targets:
        print("no failed records")
        return 0
    for pid in targets:
        row = rows[pid]
        task = queue.load_task(schema.task_path(root, row["task_id"])) if row.get("task_id") else None
        if task is None:
            print(f"{pid}: task file not found, skipped")
            continue
        task["status"] = "queued"   # 重新入队，由 worker 从 error_stage 续跑
        queue.save_task(root, task)
        print(f"{pid}: re-queued (failed at {row.get('error_stage') or '?'}: {row.get('error','')[:50]})")
    results = run.run_once(root)
    return 0 if all(s != schema.FAILED for _, s in results) else 1


if __name__ == "__main__":
    sys.exit(main())
