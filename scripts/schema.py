# -*- coding: utf-8 -*-
"""共享约定：状态枚举、csv 列名、目录/文件命名、数据根解析、凭据。"""
import hashlib
import os
from datetime import datetime, timezone

# 论文级状态机（processed.csv 的 stage 列）
STAGES = ["registered", "fetching", "converting", "enriching",
          "summarizing", "cataloging", "done"]
FAILED = "failed"
# summarizing 非本阶段：流水线实际推进顺序（跳过 summarize）
PIPELINE = ["registered", "fetching", "converting", "enriching", "cataloging", "done"]

# 任务级状态（_queue/<task-id>.json 的 status 列）
TASK_STATUSES = ["queued", "running", "done", "duplicate", "rejected"]

# processed.csv 列
CSV_FIELDS = ["id", "task_id", "stage", "md_sha256", "pdf_sha256",
              "summary_file", "summary_hash", "source", "error", "error_stage",
              "created_at", "updated_at"]

# 数据根内命名
QUEUE_DIR = "_queue"
INBOX_DIR = "_inbox"
INPUT_DIR = "input"          # _queue/input/<task-id>/ 认领暂存
CSV_FILE = "processed.csv"
EVENTS_LOG = "events.log"
CATALOG_JSON = "catalog.json"
CATALOG_MD = "catalog.md"
MINERU_TOKEN_FILE = ".mineru_token"
MINERU_STATE_FILE = ".mineru_state.json"   # <id>/ 内, MinerU 批内子状态承载

ID_MAX_LEN = 64

_CODE_ROOT = os.path.dirname(os.path.abspath(__file__))
# 代码根 <repo>/autopaper/scripts/；默认数据根 <repo>/references/reference-works/
_DEFAULT_ROOT = os.path.join(os.path.dirname(os.path.dirname(_CODE_ROOT)),
                             "references", "reference-works")


def now_str():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def resolve_root(root=None):
    """数据根解析：参数 > 环境变量 REFERENCE_WORKS > 默认 references/reference-works/。"""
    r = root or os.environ.get("REFERENCE_WORKS") or _DEFAULT_ROOT
    r = os.path.abspath(r)
    return r


def ensure_root(root):
    for d in (root, queue_dir(root), inbox_dir(root), input_dir(root)):
        os.makedirs(d, exist_ok=True)
    return root


def queue_dir(root):
    return os.path.join(root, QUEUE_DIR)


def inbox_dir(root):
    return os.path.join(root, INBOX_DIR)


def input_dir(root):
    return os.path.join(root, QUEUE_DIR, INPUT_DIR)


def csv_path(root):
    return os.path.join(root, CSV_FILE)


def events_path(root):
    return os.path.join(root, EVENTS_LOG)


def paper_dir(root, paper_id):
    return os.path.join(root, paper_id)


def task_path(root, task_id):
    return os.path.join(queue_dir(root), task_id + ".json")


def load_token(root, env_name, file_name):
    """环境变量优先，其次 <root>/<file_name>（权限 600）。"""
    tok = os.environ.get(env_name)
    if tok:
        return tok.strip()
    p = os.path.join(root, file_name)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def mineru_token(root):
    return load_token(root, "MINERU_TOKEN", MINERU_TOKEN_FILE)


def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
