#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enrich.py：抓题录 → 写 meta.json（§3.3）。幂等：已登记字段不重复抓取；不改流水线 stage。"""
import argparse
import json
import os
import re
import sys

import schema
import registry
import sources

SUMMARY_FILE = "summary.md"


def meta_path(root, paper_id):
    return os.path.join(schema.paper_dir(root, paper_id), "meta.json")


def load_meta(root, paper_id):
    p = meta_path(root, paper_id)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_meta(root, paper_id, meta):
    meta["updated_at"] = schema.now_str()
    p = meta_path(root, paper_id)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def summary_path(root, paper_id):
    return os.path.join(schema.paper_dir(root, paper_id), SUMMARY_FILE)


def parse_summary(text):
    """解析 summary.md：frontmatter 键值 + 一级标题 + `## Tags` 段。纯函数。"""
    front, body = {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                front[k.strip()] = v.strip().strip("[]")
        body = m.group(2)
    title = None
    mt = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    if mt:
        title = mt.group(1)
    tags = []
    mt_tags = re.search(r"^##\s*Tags\s*$(.*?)(?=^##\s|\Z)", body, re.M | re.S)
    if mt_tags:
        for tok in re.split(r"[,\n]", mt_tags.group(1)):
            tok = tok.strip().lstrip("-*# ").strip()
            if tok:
                tags.append(tok)
    return {"title": title, "tags": tags, "frontmatter": front,
            "md_sha256": front.get("md_sha256"), "model": front.get("model"),
            "generated_at": front.get("generated_at")}


def load_summary(root, paper_id):
    """读取 <id>/summary.md；不存在返回 None，否则附加 file/sha256。"""
    p = summary_path(root, paper_id)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        info = parse_summary(f.read())
    info["file"] = SUMMARY_FILE
    info["sha256"] = schema.sha256_file(p)
    return info


def init_meta(root, paper_id, task, fetch_info):
    """fetching 阶段后由 worker 调用：建立/更新 meta.json 的事实字段。"""
    meta = load_meta(root, paper_id) or {
        "id": paper_id, "aliases": [], "tags": [],
        "created_at": schema.now_str(),
    }
    if task.get("doi"):
        meta.setdefault("web", {})["doi"] = f"https://doi.org/{task['doi']}"
        meta["doi"] = task["doi"]
    meta["origin"] = {"by": task.get("submitted_by") or {"kind": "unattributed"},
                      "context": task.get("context", ""),
                      "task_id": task.get("task_id")}
    if fetch_info.get("pdf"):
        meta["pdf"] = fetch_info["pdf"]
    if fetch_info.get("repo"):
        meta["repo"] = fetch_info["repo"]
    if fetch_info.get("support") is not None:
        meta["support"] = fetch_info["support"]
    save_meta(root, paper_id, meta)
    return meta


def enrich(root, paper_id):
    """抓题录并合并进 meta.json。返回 meta。幂等：已有 title 不重复抓。"""
    meta = load_meta(root, paper_id) or {"id": paper_id, "aliases": [], "tags": [],
                                         "created_at": schema.now_str()}
    if not meta.get("title"):
        bib = None
        if meta.get("doi"):  # 显式 DOI 优先走 Crossref
            bib = sources.fetch_crossref(meta["doi"])
        if bib is None:
            bib = sources.fetch_biblio(paper_id)
        if bib:
            for k in ("title", "authors", "year", "venue", "abstract"):
                if bib.get(k) and not meta.get(k):
                    meta[k] = bib[k]
            if bib.get("web"):
                for wk, wv in bib["web"].items():
                    if wv and not meta.setdefault("web", {}).get(wk):
                        meta["web"][wk] = wv
        else:
            meta.setdefault("enrich_note", "bibliographic fetch failed or no adapter; left empty for manual fill")
    pdir = schema.paper_dir(root, paper_id)
    md = os.path.join(pdir, f"{paper_id}.md")
    if os.path.exists(md) and not meta.get("markdown"):
        meta["markdown"] = {"file": f"{paper_id}.md",
                            "sha256": schema.sha256_file(md),
                            "parsed_at": schema.now_str()}
    summ = load_summary(root, paper_id)
    if summ:
        meta["summary"] = {"file": summ["file"], "sha256": summ["sha256"],
                           "model": summ.get("model"), "generated_at": summ.get("generated_at")}
    save_meta(root, paper_id, meta)
    return meta


def main(argv=None):
    p = argparse.ArgumentParser(description="enrich: fetch bibliographic metadata into meta.json")
    p.add_argument("ids", nargs="*", help="paper ids (default: all non-failed)")
    p.add_argument("--root", default=None)
    args = p.parse_args(argv)
    root = schema.resolve_root(args.root)
    rows = registry.load(root)
    ids = args.ids or [i for i, r in rows.items() if r.get("stage") != schema.FAILED]
    for pid in ids:
        meta = enrich(root, pid)
        # enrich 只补 meta.json，不改流水线 stage（旧实现会把 done 论文打回 enriching）
        print(f"{pid}: title={meta.get('title')!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
