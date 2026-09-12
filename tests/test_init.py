# -*- coding: utf-8 -*-
"""init.sh 数据根初始化单测（跑真实 shell）：python3 autopaper/tests/test_init.py"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CODE_ROOT = os.path.abspath(os.path.join(HERE, ".."))
INIT = os.path.join(CODE_ROOT, "init.sh")
sys.path.insert(0, os.path.join(CODE_ROOT, "scripts"))

import schema


def run(cwd, *args):
    return subprocess.run(["bash", INIT, *args], cwd=cwd, capture_output=True, text=True)


def test_init_structure():
    parent = tempfile.mkdtemp(prefix="autopaper-init-")
    r = run(parent)
    assert r.returncode == 0, r.stderr
    root = os.path.join(parent, "reference-works")
    assert os.path.isdir(os.path.join(root, "_inbox"))
    assert os.path.isdir(os.path.join(root, "_queue", "input"))
    # 表头必须与 schema.CSV_FIELDS 一致（防止 sh 里的硬编码漂移）
    header = open(os.path.join(root, "processed.csv"), encoding="utf-8").read().strip()
    assert header.split(",") == schema.CSV_FIELDS, header
    assert os.path.exists(os.path.join(root, "events.log"))
    assert json.load(open(os.path.join(root, "catalog.json"), encoding="utf-8")) == []
    assert open(os.path.join(root, "catalog.md"), encoding="utf-8").read().startswith("# Literature Catalog")
    print("test_init_structure: OK")


def test_specified_dir_and_idempotent():
    parent = tempfile.mkdtemp(prefix="autopaper-init-")
    root = os.path.join(parent, "custom-root")
    assert run(parent, root).returncode == 0
    assert os.path.isdir(os.path.join(root, "_queue", "input"))
    # 已有数据不得被覆盖
    with open(os.path.join(root, "processed.csv"), "a", encoding="utf-8") as f:
        f.write("2504.08066,T-1-1,done,,,,,,arxiv_id:2504.08066,,,\n")
    with open(os.path.join(root, "events.log"), "a", encoding="utf-8") as f:
        f.write("sentinel\n")
    r = run(parent, "--root", root)
    assert r.returncode == 0, r.stderr
    assert "2504.08066" in open(os.path.join(root, "processed.csv"), encoding="utf-8").read()
    assert open(os.path.join(root, "events.log"), encoding="utf-8").read() == "sentinel\n"
    print("test_specified_dir_and_idempotent: OK")


if __name__ == "__main__":
    test_init_structure()
    test_specified_dir_and_idempotent()
    print("ALL OK")
