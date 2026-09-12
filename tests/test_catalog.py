# -*- coding: utf-8 -*-
"""enrich.parse_summary / catalog 摘要与 tags 归集单测（无网络）：python3 autopaper/tests/test_catalog.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import schema
import registry
import enrich
import catalog

SUMMARY = """---
id: 2504.08066
md_sha256: abc123
model: test-model
generated_at: 2026-09-12 10:00:00
revisions: []
---
# A Test Paper

> 生成于 2026-09-12 · 标识符 `2504.08066`

## 基本信息
## 一句话
一句话内容。

## Tags
llm, agents
- evaluation
"""


def test_parse_summary():
    info = enrich.parse_summary(SUMMARY)
    assert info["title"] == "A Test Paper"
    assert info["md_sha256"] == "abc123"
    assert info["model"] == "test-model"
    assert info["generated_at"] == "2026-09-12 10:00:00"
    assert info["tags"] == ["llm", "agents", "evaluation"], info["tags"]
    # 无 frontmatter / 无 Tags 段也不炸
    assert enrich.parse_summary("# T\n\nbody\n")["tags"] == []
    print("test_parse_summary: OK")


def test_catalog_summary_wiring():
    root = schema.ensure_root(tempfile.mkdtemp(prefix="autopaper-catalog-"))
    pid = "2504.08066"
    registry.register(root, {"task_id": "T-1-1"}, pid, source_str="arxiv_id:2504.08066")
    registry.update(root, pid, stage="done")
    pdir = schema.paper_dir(root, pid)
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"id": pid, "title": "A Test Paper", "year": 2025, "tags": ["meta-tag"]}, f)
    with open(os.path.join(pdir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(SUMMARY)

    entries = catalog.write_catalog(root)
    e = entries[0]
    assert e["summary"] == "summary.md" and e["summary_hash"], e
    assert e["tags"] == ["llm", "agents", "evaluation"], e["tags"]  # summary 优先于 meta.tags

    row = registry.get(root, pid)
    assert row["summary_file"] == "summary.md" and row["summary_hash"] == enrich.load_summary(root, pid)["sha256"]

    md = open(os.path.join(root, schema.CATALOG_MD), encoding="utf-8").read()
    assert "| id | title | year | tags | summary | stage |" in md
    assert "summary.md" in md and "llm, agents, evaluation" in md
    cats = json.load(open(os.path.join(root, schema.CATALOG_JSON), encoding="utf-8"))
    assert cats[0]["summary"] == "summary.md"

    # 幂等：再跑不改变
    before = open(os.path.join(root, schema.CATALOG_MD), encoding="utf-8").read()
    catalog.write_catalog(root)
    assert open(os.path.join(root, schema.CATALOG_MD), encoding="utf-8").read() == before

    # 无 summary 的论文：tags 回退 meta，summary 列为空
    registry.register(root, {"task_id": "T-2-2"}, "2504.99999", source_str="arxiv_id:2504.99999")
    pdir2 = schema.paper_dir(root, "2504.99999")
    os.makedirs(pdir2, exist_ok=True)
    with open(os.path.join(pdir2, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "2504.99999", "tags": ["only-meta"]}, f)
    entries = catalog.write_catalog(root)
    e2 = [x for x in entries if x["id"] == "2504.99999"][0]
    assert e2["summary"] is None and e2["tags"] == ["only-meta"]
    assert registry.get(root, "2504.99999")["summary_file"] == ""
    print("test_catalog_summary_wiring: OK")


if __name__ == "__main__":
    test_parse_summary()
    test_catalog_summary_wiring()
    print("ALL OK")
