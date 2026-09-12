# -*- coding: utf-8 -*-
"""id 生成（§3.0 8 级规则），纯函数：无网络、无文件副作用。

入口：
  classify(value) -> source dict {type, value}   # 判来源类型，纯串判定
  identify(source, content_sha=None) -> paper_id
"""
import re
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from schema import ID_MAX_LEN, sha256_str

ARXIV_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
ARXIV_OLD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.-]*/\d{7}(v\d+)?$")   # 旧式 arXiv: cs/0701001, math.GT/0309136
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
    """URL -> arXiv 原始标识符（新式 2504.08066v2 / 旧式 cs/0701001）。"""
    m = re.search(
        r"arxiv\.org/(?:abs|pdf|html)/([\w.-]+/\d{7}(?:v\d+)?|\d{4}\.\d{4,5}(?:v\d+)?)", url)
    return m.group(1) if m else None


def _arxiv_old_id(raw):
    """旧式 arXiv 标识符 -> 路径安全的 paper id：cs/0701001 -> arxiv-cs-0701001。"""
    return _sanitize("arxiv-" + raw)


def _arxiv_url_id(url):
    raw = _arxiv_from_url(url)
    if not raw:
        return None
    return raw if ARXIV_RE.match(raw) else _arxiv_old_id(raw)


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


# ---- 来源规则表：一条来源 = 一条规则（id 识别 + 下载地址），加来源只需 append 进 RULES ----

def _no_stem(stem):
    return None


def _no_url(url):
    return None


def _no_pdf(source, paper_id):
    return None


@dataclass(frozen=True)
class SourceRule:
    """一条来源规则，三个钩子任一可缺省（返回 None 即不匹配）。

    stem_id: 文件名/URL 末段 -> id；url_id: 完整 URL -> id；
    pdf_url: (source, paper_id) -> 下载地址。
    """
    name: str
    stem_id: Callable[[str], Optional[str]] = _no_stem
    url_id: Callable[[str], Optional[str]] = _no_url
    pdf_url: Callable[[dict, str], Optional[str]] = _no_pdf


def _arxiv_stem_id(stem):
    return stem if ARXIV_RE.match(stem) else None


def _arxiv_pdf_url(source, paper_id):
    t, v = source["type"], source["value"]
    if t == "arxiv_id":
        return f"https://arxiv.org/pdf/{v}"          # 旧式 id 本身即含 cs/0701001
    if t == "url":
        raw = _arxiv_from_url(v)
        if raw:
            return f"https://arxiv.org/pdf/{raw}"
    return None


def _biorxiv_stem_id(stem):
    # bioRxiv: 文件名里 / 常写成 _
    return stem if BIORXIV_RE.match(stem) else None


def _biorxiv_pdf_url(source, paper_id):
    if source["type"] == "url" and _biorxiv_from_url(source["value"]):
        host = "medrxiv.org" if "medrxiv" in source["value"].lower() else "biorxiv.org"
        return f"https://www.{host}/content/10.1101/{paper_id}.full.pdf"
    return None


def _generic_pdf_url(source, paper_id):
    if source["type"] == "url" and source["value"].lower().split("?")[0].endswith(".pdf"):
        return source["value"]
    return None


def _doi_stem_id(stem):
    if DOI_RE.match(stem):
        return _sanitize("doi-" + stem.replace("_", "/"))
    return None


def _doi_url_id(url):
    m = re.search(r"doi\.org/(10\.\S+)", url)
    return _sanitize("doi-" + m.group(1)) if m else None


def _doi_pdf_url(source, paper_id):
    # arXiv DOI 可直接推 PDF；其余 DOI 由 fetch 阶段的 Crossref 回退处理（sources.find_pdf_url）
    prefix = "doi-10.48550-arxiv."
    if paper_id.startswith(prefix):
        return "https://arxiv.org/pdf/" + paper_id[len(prefix):]
    return None


def _github_url_id(url):
    if re.match(r"^https?://(?:www\.)?github\.com/", url):
        return repo_id_from_url(url)
    return None


# 顺序 = 判定优先级（当前语义：arxiv → 通用 .pdf URL → biorxiv → chemrxiv → doi → github）
RULES = [
    SourceRule("arxiv", stem_id=_arxiv_stem_id, url_id=_arxiv_url_id,
               pdf_url=_arxiv_pdf_url),
    SourceRule("generic-pdf", pdf_url=_generic_pdf_url),
    SourceRule("biorxiv", stem_id=_biorxiv_stem_id, url_id=_biorxiv_from_url,
               pdf_url=_biorxiv_pdf_url),
    SourceRule("chemrxiv", stem_id=normalize_chemrxiv, url_id=_chemrxiv_from_url),
    SourceRule("doi", stem_id=_doi_stem_id, url_id=_doi_url_id, pdf_url=_doi_pdf_url),
    SourceRule("github", url_id=_github_url_id),
]


def id_from_name(name):
    """① 文件名/URL 末段识别（规则 1–5），未命中返回 None。"""
    stem = _stem(name)
    if not stem:
        return None
    for rule in RULES:
        hit = rule.stem_id(stem)
        if hit:
            return hit
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
    if ARXIV_RE.match(v) or ARXIV_OLD_RE.match(v):
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
        return _arxiv_old_id(v) if ARXIV_OLD_RE.match(v) else v
    if t in ("url", "pdf_path"):
        hit = id_from_name(v)
        if hit:
            return hit
    if t == "url":
        for rule in RULES:
            hit = rule.url_id(v)
            if hit:
                return hit
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
    """由 source 推出 PDF 下载地址；无法下载返回 None。规则见 RULES。"""
    for rule in RULES:
        url = rule.pdf_url(source, paper_id)
        if url:
            return url
    return None


def resolve(source, content_sha=None, doi=None):
    """来源/链接 -> (paper_id, pdf_url)：id 与下载规则一次取出。"""
    paper_id = identify(source, content_sha=content_sha, doi=doi)
    return paper_id, pdf_url_for(source, paper_id)
