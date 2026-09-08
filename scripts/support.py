#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""support.py：附加材料 add/list（§3.1）。"""
import argparse
import sys

import schema
import fetch
from enrich import load_meta, save_meta


def main(argv=None):
    p = argparse.ArgumentParser(description="manage supplementary materials")
    p.add_argument("--root", default=None)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("id")
    a.add_argument("url")
    a.add_argument("--name", default=None)
    l = sub.add_parser("list")
    l.add_argument("id")
    args = p.parse_args(argv)
    root = schema.resolve_root(args.root)
    pdir = schema.paper_dir(root, args.id)
    if args.cmd == "add":
        entry = fetch.add_support(pdir, args.url, name=args.name)
        meta = load_meta(root, args.id) or {"id": args.id, "aliases": [], "tags": [],
                                            "created_at": schema.now_str()}
        meta.setdefault("support", []).append(entry)
        save_meta(root, args.id, meta)
        print(f"support added: {entry['local']} sha256={entry['sha256'][:12]}...")
    else:
        meta = load_meta(root, args.id) or {}
        for e in meta.get("support", []):
            print(f"{e.get('name')}: {e.get('local')} <- {e.get('source')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
