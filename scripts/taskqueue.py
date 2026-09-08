# -*- coding: utf-8 -*-
"""_queue/ _inbox/ 任务文件生命周期、.tmp 原子写、events.log（§3.0）。"""
import json
import os
import re
import shutil
import time

import schema

_seq = 0
TASK_FILE_RE = re.compile(r"^T-\d+-\d+\.json$")


def new_task_id():
    global _seq
    ms = int(time.time() * 1000)
    _seq += 1
    return f"T-{ms}-{_seq}"


def atomic_write_json(path, obj):
    tmp = os.path.join(os.path.dirname(path), ".tmp-" + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_task(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize_task(raw):
    """补齐任务请求缺省字段（§3.0：除 task_id 与 source 外均可选）。"""
    t = dict(raw)
    t.setdefault("task_id", new_task_id())
    t.setdefault("submitted_by", {"kind": "unattributed"})
    t.setdefault("context", "")
    t.setdefault("repo", [])
    t.setdefault("support", [])
    t.setdefault("doi", None)
    if isinstance(t.get("repo"), str):
        t["repo"] = [t["repo"]]
    t.setdefault("status", "queued")
    t.setdefault("paper_id", None)
    t.setdefault("created_at", schema.now_str())
    t["updated_at"] = schema.now_str()
    return t


def create_task(root, source, repo=None, support=None, submitted_by=None,
                context="", task_id=None, doi=None):
    schema.ensure_root(root)
    task = normalize_task({
        "task_id": task_id or new_task_id(),
        "submitted_by": submitted_by or {"kind": "unattributed"},
        "context": context,
        "source": source,
        "repo": repo or [],
        "support": support or [],
        "doi": doi,
        "created_at": schema.now_str(),
    })
    atomic_write_json(schema.task_path(root, task["task_id"]), task)
    return task


def save_task(root, task):
    task["updated_at"] = schema.now_str()
    atomic_write_json(schema.task_path(root, task["task_id"]), task)


def list_tasks(root, status=None):
    """按文件名时间序 FIFO 列出正式任务文件（忽略 .tmp-*）。"""
    qdir = schema.queue_dir(root)
    if not os.path.isdir(qdir):
        return []
    out = []
    for fn in sorted(os.listdir(qdir)):
        if not TASK_FILE_RE.match(fn):
            continue
        task = load_task(os.path.join(qdir, fn))
        if status is None or task.get("status") in (status if isinstance(status, (list, tuple)) else [status]):
            out.append(task)
    return out


def log_event(root, event, **fields):
    line = f"{schema.now_str()} {event}"
    for k, v in fields.items():
        if v is not None:
            line += f" {k}={v}"
    with open(schema.events_path(root), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _claim(root, task_id, files):
    """把 _inbox 条目原子 mv 到 _queue/input/<task-id>/ 暂存。返回 {原名: 新路径}。"""
    dest_dir = os.path.join(schema.input_dir(root), task_id)
    os.makedirs(dest_dir, exist_ok=True)
    moved = {}
    for p in files:
        d = os.path.join(dest_dir, os.path.basename(p))
        shutil.move(p, d)
        moved[os.path.basename(p)] = d
    return moved


def scan_inbox(root):
    """扫描 _inbox 并认领：成对（pdf+json）、匿名 pdf、.url/.txt、裸 json。

    返回新创建的任务 list（status=queued，source 已指向暂存文件或 url）。
    半对（json 无主名 pdf 且未自带 source）本轮跳过。
    """
    ibox = schema.inbox_dir(root)
    if not os.path.isdir(ibox):
        return []
    names = [n for n in sorted(os.listdir(ibox))
             if not n.startswith(".") and not n.startswith(".tmp-")]
    pdfs = {n: os.path.join(ibox, n) for n in names if n.lower().endswith(".pdf")}
    jsons = {n: os.path.join(ibox, n) for n in names if n.lower().endswith(".json")}
    urls = {n: os.path.join(ibox, n) for n in names if n.lower().endswith((".url", ".txt"))}
    consumed, tasks = set(), []

    def stem(n):
        return n.rsplit(".", 1)[0]

    # 1) json（含成对投递）
    for jn, jp in jsons.items():
        raw = load_task(jp)
        src = raw.get("source")
        pair_pdf = None
        # 显式引用 _inbox 内其他 pdf 优先，其次同主名推断
        if src and src.get("type") == "pdf_path":
            cand = os.path.basename(src["value"])
            if cand in pdfs:
                pair_pdf = cand
        if pair_pdf is None and stem(jn) in [stem(p) for p in pdfs]:
            pair_pdf = next(p for p in pdfs if stem(p) == stem(jn))
        if pair_pdf is None and not src:
            continue  # 半对等待
        task_id = raw.get("task_id") or new_task_id()
        files = [jp] + ([pdfs[pair_pdf]] if pair_pdf else [])
        moved = _claim(root, task_id, files)
        consumed.update(os.path.basename(p) for p in files)
        if pair_pdf:
            raw["source"] = {"type": "pdf_path", "value": moved[pair_pdf]}
        task = normalize_task({**raw, "task_id": task_id})
        atomic_write_json(schema.task_path(root, task_id), task)
        log_event(root, "inbox-claim", task_id=task_id, kind="json")
        tasks.append(task)

    # 2) 匿名 pdf
    for pn, pp in pdfs.items():
        if pn in consumed:
            continue
        task_id = new_task_id()
        moved = _claim(root, task_id, [pp])
        task = create_task(
            root, {"type": "pdf_path", "value": moved[pn]},
            submitted_by={"kind": "unattributed", "name": "_inbox"},
            task_id=task_id)
        log_event(root, "inbox-claim", task_id=task_id, kind="pdf")
        tasks.append(task)

    # 3) .url / .txt：单行 URL 或 arXiv id（忽略空行与 # 注释）
    for un, up in urls.items():
        if un in consumed:
            continue
        with open(up, encoding="utf-8") as f:
            line = next((l.strip() for l in f if l.strip() and not l.startswith("#")), "")
        if not line:
            os.remove(up)
            continue
        from identity import classify
        os.remove(up)
        task = create_task(root, classify(line),
                           submitted_by={"kind": "unattributed", "name": "_inbox"})
        log_event(root, "inbox-claim", task_id=task["task_id"], kind="url")
        tasks.append(task)
    return tasks


def cleanup_input(root, task_id):
    d = os.path.join(schema.input_dir(root), task_id)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
