# -*- coding: utf-8 -*-
"""id 生成（§3.0 8 级规则），纯函数：无网络、无文件副作用。

入口：
  classify(value) -> source dict {type, value}   # 判来源类型，纯串判定
  identify(source, content_sha=None) -> paper_id
"""
import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from schema import ID_MAX_LEN, sha256_str

ARXIV_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
BIORXIV_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{4,7}(v\d+)?$")
CHEMRXIV_RE = re.compile(r"^chemrxiv[._]\d{6,10}([._]v\d+)?$", re.I)
DOI_RE = re.compile(r"^10\.\d{4,9}[/_.]\S+$")
OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def normalize_url(url):
    """去 scheme 差异 / fragment / 尾斜杠 / utm_* 跟踪参数；host 小写。"""
    url = url.strip()
    p = urlparse(url)
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    q = urlencode([(k, v) for k, v in parse_qsl(p.query) if not k.startswith("utm_")])
    path = p.path.rstrip("/")
    return urlunparse(("https", host, path, "", q, ""))


def _sanitize(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9._-]", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-.")
    return s[:ID_MAX_LEN]


def _arxiv_from_url(url):
    m = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
    return m.group(1) if m else None


def _biorxiv_from_url(url):
    m = re.search(r"(?:biorxiv|medrxiv)\.org/.*?(10\.1101/(\d{4}\.\d{2}\.\d{2}\.\d{4,7}(?:v\d+)?))", url)
    return m.group(2) if m else None


def _chemrxiv_from_url(url):
    m = re.search(r"chemrxiv[._](\d{6,10})(?:[._/]v(\d+))?", url, re.I)
    if not m:
        return None
    return f"chemrxiv.{m.group(1)}" + (f".v{m.group(2)}" if m.group(2) else "")


def normalize_chemrxiv(stem):
    """chemrxiv.15003852_v1 -> chemrxiv.15003852.v1（_v<n> 规范化为 .v<n>）。"""
    m = re.match(r"^chemrxiv[._](\d{6,10})(?:[._]v(\d+))?$", stem, re.I)
    if not m:
        return None
    return f"chemrxiv.{m.group(1)}" + (f".v{m.group(2)}" if m.group(2) else "")


def _stem(name):
    """URL 末段或文件名，去扩展名/query。"""
    name = name.split("?")[0].split("#")[0].rstrip("/")
    base = name.rsplit("/", 1)[-1]
    if base.lower().endswith((".pdf", ".url", ".txt")):
        base = base.rsplit(".", 1)[0]
    return base


def id_from_name(name):
    """① 文件名/URL 末段识别（规则 1–5），未命中返回 None。"""
    stem = _stem(name)
    if not stem:
        return None
    if ARXIV_RE.match(stem):
        return stem
    # bioRxiv: 文件名里 / 常写成 _
    if BIORXIV_RE.match(stem):
        return stem
    cx = normalize_chemrxiv(stem)
    if cx:
        return cx
    if DOI_RE.match(stem):
        return _sanitize("doi-" + stem.replace("_", "/"))
    return None


def normalize_repo_url(s):
    """owner/repo -> https://github.com/owner/repo；GitHub URL 规范化；其余原样。"""
    s = s.strip().rstrip("/")
    m = OWNER_REPO_RE.match(s)
    if m and "://" not in s:
        return f"https://github.com/{s}"
    if s.endswith(".git"):
        s = s[:-4]
    m = re.match(r"^https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+)$", s)
    if m:
        return f"https://github.com/{m.group(1)}/{m.group(2)}"
    return s


def repo_id_from_url(url):
    """规则 5：repo-<owner>-<name>，全小写。"""
    norm = normalize_repo_url(url)
    m = re.match(r"^https://github\.com/([\w.-]+)/([\w.-]+)$", norm)
    if m:
        return _sanitize(f"repo-{m.group(1)}-{m.group(2)}")
    parts = [p for p in re.split(r"[/:]", norm) if p]
    if len(parts) >= 2:
        return _sanitize(f"repo-{parts[-2]}-{parts[-1]}")
    return None


def classify(value):
    """把投递的字符串归类为 source dict（type ∈ arxiv_id|url|pdf_path|repo_only）。"""
    v = value.strip()
    if ARXIV_RE.match(v):
        return {"type": "arxiv_id", "value": v}
    if v.startswith(("http://", "https://")):
        return {"type": "url", "value": v}
    # 显式本地路径（./ ../ 或绝对路径）不当作 owner/repo
    if v.startswith(("./", "../")) or v.startswith("/"):
        return {"type": "pdf_path", "value": v}
    if OWNER_REPO_RE.match(v):
        # 末段带扩展名（如 dir/paper.pdf）是本地文件，不是 owner/repo
        if "." in v.rsplit("/", 1)[-1]:
            return {"type": "pdf_path", "value": v}
        return {"type": "repo_only", "value": normalize_repo_url(v)}
    return {"type": "pdf_path", "value": v}


def doi_id(doi):
    """显式 DOI -> doi-<规范化>（小写，非 [a-z0-9._-] 转 -）。"""
    return _sanitize("doi-" + doi.strip())


def identify(source, content_sha=None, doi=None):
    """按 8 级规则生成 paper_id（确定可复算）。

    source: {"type": ..., "value": ...}；本地文件回退（规则 6）需 content_sha。
    显式 doi（--doi / 任务 json 的 "doi" 字段）优先于文件名识别与一切回退。
    """
    if doi:
        return doi_id(doi)
    t, v = source["type"], source["value"].strip()
    # ① 文件名/URL 末段优先（规则 1–4 的形态可能出现在任意名字里）
    if t == "arxiv_id":
        return v
    if t in ("url", "pdf_path"):
        hit = id_from_name(v)
        if hit:
            return hit
    if t == "url":
        ax = _arxiv_from_url(v)
        if ax:
            return ax
        bx = _biorxiv_from_url(v)
        if bx:
            return bx
        cx = _chemrxiv_from_url(v)
        if cx:
            return cx
        m = re.search(r"doi\.org/(10\.\S+)", v)
        if m:
            return _sanitize("doi-" + m.group(1))
        gh = re.match(r"^https?://(?:www\.)?github\.com/", v)
        if gh:
            rid = repo_id_from_url(v)
            if rid:
                return rid
        # 规则 7
        return "web-" + sha256_str(normalize_url(v))[:12]
    if t == "pdf_path":
        # 规则 6
        if not content_sha:
            raise ValueError("content_sha required for local-file fallback id")
        return "file-" + content_sha[:12]
    if t == "repo_only":
        rid = repo_id_from_url(v)
        if rid:
            return rid
        return "misc-" + sha256_str(v.lower())[:12]
    # 规则 8 兜底
    return "misc-" + sha256_str(v.lower())[:12]


def pdf_url_for(source, paper_id):
    """由 source 推出 PDF 下载地址；无法下载返回 None。"""
    t, v = source["type"], source["value"]
    if t == "arxiv_id" or (t == "url" and _arxiv_from_url(v)):
        return f"https://arxiv.org/pdf/{paper_id}"
    if t == "url" and v.lower().split("?")[0].endswith(".pdf"):
        return v
    if t == "url" and _biorxiv_from_url(v):
        return f"https://www.biorxiv.org/content/10.1101/{paper_id}.full.pdf"
    return None
