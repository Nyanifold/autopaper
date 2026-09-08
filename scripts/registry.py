# -*- coding: utf-8 -*-
"""processed.csv 读写 / 查重 / 状态迁移（§4）。判定为纯函数，IO 分离。"""
import csv
import os

import schema


def load(root):
    p = schema.csv_path(root)
    if not os.path.exists(p):
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def save(root, rows):
    p = schema.csv_path(root)
    tmp = p + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=schema.CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for rec in sorted(rows.values(), key=lambda r: r["id"]):
            w.writerow({k: rec.get(k, "") for k in schema.CSV_FIELDS})
    os.replace(tmp, p)


def find(rows, paper_id=None, pdf_sha256=None, repo_url=None, exclude_task=None):
    """查重纯判定：键 = id；已得 sha256 加查 sha256；repo-only 用规范化 repo URL。
    返回 (命中行, 命中方式) 或 (None, None)。"""
    if paper_id and paper_id in rows:
        return rows[paper_id], "id"
    if pdf_sha256:
        for r in rows.values():
            if r.get("pdf_sha256") == pdf_sha256:
                return r, "pdf_sha256"
    if repo_url:
        for r in rows.values():
            if repo_url in (r.get("source") or ""):
                return r, "repo"
    return None, None


def register(root, task, paper_id, source_str=""):
    """先登记后干活：落 csv 行（registered，含 task_id）。返回行。"""
    rows = load(root)
    now = schema.now_str()
    row = {"id": paper_id, "task_id": task["task_id"], "stage": "registered",
           "source": source_str, "created_at": now, "updated_at": now,
           "md_sha256": "", "pdf_sha256": "", "summary_file": "",
           "summary_hash": "", "error": ""}
    rows[paper_id] = row
    save(root, rows)
    return row


def update(root, paper_id, **fields):
    rows = load(root)
    row = rows[paper_id]
    row.update(fields)
    row["updated_at"] = schema.now_str()
    save(root, rows)
    return row


def set_stage(root, paper_id, stage, **fields):
    return update(root, paper_id, stage=stage, **fields)


def fail(root, paper_id, reason):
    return update(root, paper_id, stage=schema.FAILED, error=reason)


def get(root, paper_id):
    return load(root).get(paper_id)
