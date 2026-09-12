# -*- coding: utf-8 -*-
"""registry.py / taskqueue.py 单测（用临时目录，无网络）：python3 autopaper/tests/test_registry.py"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import schema
import registry
import taskqueue as queue


def fresh_root():
    return schema.ensure_root(tempfile.mkdtemp(prefix="autopaper-test-"))


def test_registry():
    root = fresh_root()
    rows = registry.load(root)
    assert rows == {}
    task = {"task_id": "T-1-1"}
    registry.register(root, task, "2504.08066", source_str="arxiv_id:2504.08066")
    rows = registry.load(root)
    assert "2504.08066" in rows and rows["2504.08066"]["stage"] == "registered"
    # 查重：id 键
    hit, how = registry.find(rows, paper_id="2504.08066")
    assert hit and how == "id"
    # 查重：pdf sha256
    registry.update(root, "2504.08066", pdf_sha256="abc123")
    hit, how = registry.find(registry.load(root), pdf_sha256="abc123")
    assert hit["id"] == "2504.08066" and how == "pdf_sha256"
    # 版本号互不判重
    hit, _ = registry.find(registry.load(root), paper_id="2504.08066v2")
    assert hit is None
    # 状态迁移与失败记录
    registry.set_stage(root, "2504.08066", "fetching")
    registry.update(root, "2504.08066", stage=schema.FAILED, error="boom", error_stage="converting")
    r = registry.get(root, "2504.08066")
    assert r["stage"] == "failed" and r["error_stage"] == "converting"
    # 列齐全
    assert set(schema.CSV_FIELDS) <= set(r.keys())

    # repo 判重精确匹配：owner/repo 不得误命中 owner/repo-v2（子串匹配的旧 bug）
    registry.register(root, {"task_id": "T-2-2"}, "repo-sakanaai-ai-scientist-v2",
                      source_str="repo_only:https://github.com/SakanaAI/AI-Scientist-v2")
    rows = registry.load(root)
    hit, how = registry.find(rows, paper_id="repo-sakanaai-ai-scientist",
                             repo_url="https://github.com/SakanaAI/AI-Scientist")
    assert hit is None, (hit, how)
    hit, how = registry.find(rows, paper_id="nope",
                             repo_url="https://github.com/SakanaAI/AI-Scientist-v2")
    assert hit["id"] == "repo-sakanaai-ai-scientist-v2" and how == "repo"
    print("test_registry: OK")


def test_queue():
    root = fresh_root()
    # 原子写 + FIFO 顺序
    t1 = queue.create_task(root, {"type": "arxiv_id", "value": "2504.08066"})
    t2 = queue.create_task(root, {"type": "arxiv_id", "value": "2504.08067"})
    assert t1["task_id"] != t2["task_id"]
    tasks = queue.list_tasks(root, status="queued")
    assert [t["task_id"] for t in tasks] == [t1["task_id"], t2["task_id"]]
    # 缺省字段补齐
    assert t1["submitted_by"] == {"kind": "unattributed"} and t1["paper_id"] is None
    # .tmp 文件被忽略
    open(os.path.join(schema.queue_dir(root), ".tmp-T-9-9.json"), "w").write("{}")
    assert len(queue.list_tasks(root)) == 2
    # events.log 追加
    queue.log_event(root, "registered", task_id=t1["task_id"], paper_id="2504.08066")
    queue.log_event(root, "done", task_id=t1["task_id"], paper_id="2504.08066")
    with open(schema.events_path(root)) as f:
        assert len(f.readlines()) == 2

    # _inbox：.url 投递
    with open(os.path.join(schema.inbox_dir(root), "note.url"), "w") as f:
        f.write("# comment\n\n2504.08066\n")
    got = queue.scan_inbox(root)
    assert any(t["source"] == {"type": "arxiv_id", "value": "2504.08066"} for t in got)

    # _inbox：匿名 pdf（认领到 _queue/input/）
    inbox_pdf = os.path.join(schema.inbox_dir(root), "2505.15047.pdf")
    with open(inbox_pdf, "wb") as f:
        f.write(b"%PDF-1.4 fake")
    got = queue.scan_inbox(root)
    anon = [t for t in got if t["source"]["type"] == "pdf_path"]
    assert anon and not os.path.exists(inbox_pdf)          # 已 mv 走
    assert os.path.isfile(anon[0]["source"]["value"])      # 暂存件在
    assert anon[0]["submitted_by"]["kind"] == "unattributed"
    # 幂等：再扫不可见
    assert queue.scan_inbox(root) == []

    # _inbox：半对 json 本轮跳过，成对后认领
    jname = os.path.join(schema.inbox_dir(root), "foo.json")
    with open(jname, "w") as f:
        json.dump({"context": "paired", "repo": ["o/r"]}, f)
    assert queue.scan_inbox(root) == []                    # 半对等待
    with open(os.path.join(schema.inbox_dir(root), "foo.pdf"), "wb") as f:
        f.write(b"%PDF fake2")
    got = queue.scan_inbox(root)
    assert len(got) == 1 and got[0]["context"] == "paired" and got[0]["repo"] == ["o/r"]
    assert got[0]["source"]["type"] == "pdf_path"
    print("test_queue: OK")




def test_add_doi():
    """add.submit --doi：受理级端到端（无网络），id 走 doi- 规则、任务 json 落 doi、判重不变。"""
    import add as add_mod
    root = fresh_root()
    pdf = os.path.join(root, "random-name.pdf")   # 文件名不规范, 无 doi 时应退化为 file-<hash>
    with open(pdf, "wb") as f:
        f.write(b"%PDF-1.4 fake doi test")
    code, task, pid, err = add_mod.submit(source_value=pdf, root=root, doi="10.1063/5.0287366")
    assert code == 0 and pid == "doi-10.1063-5.0287366", (code, pid, err)
    assert task["doi"] == "10.1063/5.0287366"
    row = registry.get(root, pid)
    assert row and row["stage"] == "registered"
    # 重复投递（同 doi）→ duplicate, code 2
    code2, _, pid2, _ = add_mod.submit(source_value=pdf, root=root, doi="10.1063/5.0287366")
    assert code2 == 2 and pid2 == pid
    # 对照：无 doi 时同内容副本走 file-<hash> 暂定 id（受理阶段 csv 尚无 pdf_sha256,
    # sha 复查在 fetch 后才兜住同字节副本——见规范 §3.0 第 4 条）
    import shutil
    copy = pdf + ".copy.pdf"
    shutil.copyfile(pdf, copy)
    code3, _, pid3, _ = add_mod.submit(source_value=copy, root=root)
    assert code3 == 0 and pid3.startswith("file-") and pid3 != pid
    print("test_add_doi: OK")

if __name__ == "__main__":
    test_registry()
    test_queue()
    test_add_doi()
    print("ALL OK")
