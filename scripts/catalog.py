#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""catalog.py：读 processed.csv × 各 meta.json → catalog.json / catalog.md（§3.5）。幂等。"""
import argparse
import json
import os
import sys
from collections import defaultdict

import schema
import registry
from enrich import load_meta, load_summary


def build(root):
    """读 processed.csv × meta.json × summary.md → entries；并把 summary 落回 CSV 两列。"""
    rows = registry.load(root)
    entries = []
    changed = False
    for pid, row in sorted(rows.items()):
        meta = load_meta(root, pid) or {}
        summ = load_summary(root, pid)
        tags = (summ or {}).get("tags") or meta.get("tags") or []
        sfile = summ["file"] if summ else ""
        shash = summ["sha256"] if summ else ""
        if row.get("summary_file", "") != sfile or row.get("summary_hash", "") != shash:
            row["summary_file"] = sfile
            row["summary_hash"] = shash
            changed = True
        entries.append({
            "id": pid,
            "title": meta.get("title"),
            "year": meta.get("year"),
            "authors": meta.get("authors") or [],
            "tags": tags,
            "stage": row.get("stage"),
            "venue": meta.get("venue"),
            "web": meta.get("web") or {},
            "summary": sfile or None,
            "summary_hash": shash or None,
        })
    if changed:
        registry.save(root, rows)
    return entries


def write_catalog(root):
    entries = build(root)
    with open(os.path.join(root, schema.CATALOG_JSON), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    lines = ["# Literature Catalog", "",
             "| id | title | year | tags | summary | stage |",
             "| --- | --- | --- | --- | --- | --- |"]
    for e in entries:
        lines.append("| {id} | {title} | {year} | {tags} | {summary} | {stage} |".format(
            id=e["id"], title=(e["title"] or "")[:80], year=e["year"] or "",
            tags=", ".join(e["tags"]), summary=e["summary"] or "", stage=e["stage"] or ""))
    by_tag = defaultdict(list)
    for e in entries:
        for t in e["tags"]:
            by_tag[t].append(e["id"])
    if by_tag:
        lines += ["", "## Index by tag"]
        for t in sorted(by_tag):
            lines.append(f"- **{t}**: " + ", ".join(sorted(by_tag[t])))
    with open(os.path.join(root, schema.CATALOG_MD), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return entries


def main(argv=None):
    p = argparse.ArgumentParser(description="build catalog.json / catalog.md")
    p.add_argument("--root", default=None)
    args = p.parse_args(argv)
    root = schema.resolve_root(args.root)
    entries = write_catalog(root)
    print(f"catalog refreshed: {len(entries)} paper(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
