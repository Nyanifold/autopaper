# -*- coding: utf-8 -*-
"""PDF 下载、repo clone、support 下载解压、sha256（§3.1）。"""
import os
import shutil
import subprocess
import tarfile
import time
import zipfile
from urllib.parse import urlsplit

import requests

import schema
import sources
from identity import normalize_repo_url, pdf_url_for

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
      "Accept": "application/pdf,*/*"}
DOWNLOAD_ATTEMPTS = 3


def _env_int(name, default=0):
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


# 单文件下载上限（字节）；0 = 不限制。环境变量 AUTOPAPER_MAX_PDF_BYTES。
PDF_MAX_BYTES = _env_int("AUTOPAPER_MAX_PDF_BYTES", 0)


class PdfTooLarge(RuntimeError):
    pass


def sha256_file(path):
    return schema.sha256_file(path)


def _unlink(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _referer(url):
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}/" if p.netloc else None


def _download_once(url, tmp, headers):
    with requests.get(url, headers=headers, timeout=300, stream=True) as resp:
        resp.raise_for_status()
        total = 0
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(65536):
                total += len(chunk)
                if PDF_MAX_BYTES and total > PDF_MAX_BYTES:
                    raise PdfTooLarge(
                        f"PDF exceeds AUTOPAPER_MAX_PDF_BYTES={PDF_MAX_BYTES}")
                f.write(chunk)


def download(url, dest, referer=None, attempts=DOWNLOAD_ATTEMPTS):
    """流式下载到 dest；失败重试 attempts 次，落 .part 再原子改名，失败清理 .part。"""
    tmp = dest + ".part"
    headers = dict(UA)
    if referer:
        headers["Referer"] = referer
    last = None
    for i in range(attempts):
        try:
            _download_once(url, tmp, headers)
        except requests.RequestException as exc:
            last = exc
            _unlink(tmp)
            if i + 1 < attempts:
                time.sleep(2 ** i)
            continue
        except PdfTooLarge:
            _unlink(tmp)
            raise
        os.replace(tmp, dest)
        return dest
    raise RuntimeError(f"download failed after {attempts} attempts: {url} ({last})")


def assert_pdf(path):
    """校验文件像 PDF（头部 1KB 内出现 %PDF-），防止把 HTML 错误页当 PDF 存下。"""
    with open(path, "rb") as f:
        head = f.read(1024)
    if b"%PDF-" not in head:
        raise RuntimeError(f"downloaded file is not a PDF (no %PDF- header): {path}")


def repo_dir_name(repo_url):
    name = normalize_repo_url(repo_url).rstrip("/")
    if name.endswith(".git"):
        name = name[:-4]
    return name.split("/")[-1].split(":")[-1]


def clone_repo(repo_url, paper_dir):
    """clone（浅）进 paper_dir，记录 {url, dir, commit}；已存在则复用。"""
    url = normalize_repo_url(repo_url)
    name = repo_dir_name(url)
    dest = os.path.join(paper_dir, name)
    if os.path.isdir(dest):
        commit = _git_rev(dest)
        return {"url": url, "dir": name, "commit": commit}
    if os.path.isdir(repo_url):  # 本地路径仓库：复制（保留 .git）
        shutil.copytree(repo_url, dest, symlinks=True)
        return {"url": url, "dir": name, "commit": _git_rev(dest)}
    subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, dest],
                   check=True, timeout=1800)
    return {"url": url, "dir": name, "commit": _git_rev(dest)}


def _git_rev(dest):
    try:
        out = subprocess.run(["git", "-C", dest, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def add_support(paper_dir, url, name=None):
    """下载附加材料；zip/tar 解压进 support/<name>/，其余保持原样。"""
    sdir = os.path.join(paper_dir, "support")
    os.makedirs(sdir, exist_ok=True)
    base = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "support.bin"
    stem = name or base.rsplit(".", 1)[0]
    raw = os.path.join(sdir, base)
    download(url, raw)
    digest = sha256_file(raw)
    entry = {"name": stem, "source": url, "local": f"support/{base}",
             "sha256": digest, "note": ""}
    target = os.path.join(sdir, stem)
    try:
        if zipfile.is_zipfile(raw):
            with zipfile.ZipFile(raw) as zf:
                zf.extractall(target)
            os.remove(raw)
            entry["local"] = f"support/{stem}/"
        elif tarfile.is_tarfile(raw):
            with tarfile.open(raw) as tf:
                tf.extractall(target, filter="data")
            os.remove(raw)
            entry["local"] = f"support/{stem}/"
    except (zipfile.BadZipFile, tarfile.TarError):
        entry["note"] = "not extractable; kept as-is"
    return entry


def fetch_paper(root, paper_id, task):
    """执行 fetching 阶段。返回 {"pdf": {...}|None, "repo": [...], "support": [...]}。

    PDF 来源：pdf_path（暂存/本地文件拷入）或 URL 下载；repo_only 无 PDF。
    """
    pdir = schema.paper_dir(root, paper_id)
    os.makedirs(pdir, exist_ok=True)
    src = task["source"]
    pdf_info = None

    if src["type"] != "repo_only":
        dest_pdf = os.path.join(pdir, f"{paper_id}.pdf")
        if src["type"] == "pdf_path":
            src_path = src["value"]
            if os.path.abspath(src_path) != os.path.abspath(dest_pdf) and not os.path.exists(dest_pdf):
                shutil.copyfile(src_path, dest_pdf)
        elif not os.path.exists(dest_pdf):
            url = pdf_url_for(src, paper_id) or sources.find_pdf_url(paper_id, task.get("doi"))
            if not url:
                raise RuntimeError(f"cannot determine PDF download URL: {src}")
            download(url, dest_pdf, referer=_referer(url))
            assert_pdf(dest_pdf)
        if os.path.exists(dest_pdf):
            pdf_info = {"local": f"{paper_id}.pdf",
                        "source": src["value"],
                        "sha256": sha256_file(dest_pdf)}

    repos = []
    for r in task.get("repo") or []:
        try:
            repos.append(clone_repo(r, pdir))
        except Exception as exc:
            print(f"  [fetch] repo clone failed {r}: {exc}")
    support = []
    for u in task.get("support") or []:
        try:
            support.append(add_support(pdir, u))
        except Exception as exc:
            print(f"  [fetch] support download failed {u}: {exc}")
    return {"pdf": pdf_info, "repo": repos, "support": support}
