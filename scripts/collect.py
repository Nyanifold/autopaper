#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect.py：一键命令——与 add.py 完全同参，受理后立即推进到 done（纯编排，无自身逻辑）。"""
import os
import sys

import schema
import add
import run


def main(argv=None):
    # 参数与 add.py 完全一致（--wait 隐含，忽略）
    args = add.build_parser().parse_args(argv)
    if args.source and args.inbox:
        print("error: <source> and --inbox are mutually exclusive", file=sys.stderr)
        return 1
    root = schema.resolve_root(args.root)
    code, task, paper_id, err = add.submit(source_value=args.source, inbox_name=args.inbox,
                                           repo=args.repo, support=args.support, root=root, doi=args.doi)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return code
    if code == 2:
        print(f"duplicate {paper_id} (already collected; no work repeated)")
        return 2
    results = run.run_once(root, only_id=paper_id)
    final = dict(results).get(paper_id, "unknown")
    if final == "done":
        print(f"done: artifacts at {schema.paper_dir(root, paper_id)}/")
        return 0
    print(f"not done (stage={final}); after fixing, run: python3 retry.py --root {root}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
