#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""status.py：打印 processed.csv 流水 + _queue 未完成任务（§4）。"""
import argparse
import sys

import schema
import registry
import taskqueue as queue


def main(argv=None):
    p = argparse.ArgumentParser(description="show status")
    p.add_argument("--root", default=None)
    args = p.parse_args(argv)
    root = schema.resolve_root(args.root)
    rows = registry.load(root)
    print("== processed.csv ==")
    for r in sorted(rows.values(), key=lambda r: r["id"]):
        print(f"{r['id']:<24} {r.get('stage',''):<12} {r.get('error','')[:60]}")
    print(f"{len(rows)} paper(s)\n== open tasks in _queue ==")
    open_tasks = queue.list_tasks(root, status=["queued", "running"])
    for t in open_tasks:
        print(f"{t['task_id']:<22} {t.get('status'):<8} paper_id={t.get('paper_id')}")
    if not open_tasks:
        print("(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
