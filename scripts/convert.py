# -*- coding: utf-8 -*-
"""MinerU 提交/轮询/下载 md+images（§3.2）。批内子状态存 <id>/.mineru_state.json。"""
import json
import os
import shutil
import time
import zipfile

import requests

import schema

API_BASE = os.environ.get("MINERU_API_BASE", "https://mineru.net/api")
POLL_INTERVAL = 5
DEFAULT_TIMEOUT = 3600
MODEL_VERSION = os.environ.get("MINERU_MODEL_VERSION", "vlm")


def _log(msg):
    print(f"[{schema.now_str()}] [mineru] {msg}", flush=True)


def _http_json(method, url, token=None, **kw):
    headers = kw.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    headers.setdefault("Accept", "*/*")
    last = None
    for attempt in range(3):
        try:
            resp = requests.request(method, url, headers=headers, timeout=60, **kw)
            if resp.status_code == 429:
                time.sleep(60)
                continue
            if resp.status_code >= 500:
                time.sleep(10)
                continue
            if resp.status_code == 200:
                try:
                    return resp.json()
                except json.JSONDecodeError:
                    return {"code": -1, "msg": f"non-JSON response: {resp.text[:200]}"}
            return {"code": -1, "msg": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        except requests.RequestException as exc:
            last = exc
            time.sleep(5)
    raise RuntimeError(f"request failed: {url} ({last})")


def _state_path(paper_dir):
    return os.path.join(paper_dir, schema.MINERU_STATE_FILE)


def _load_state(paper_dir):
    p = _state_path(paper_dir)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_state(paper_dir, state):
    with open(_state_path(paper_dir), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def convert(root, paper_id, timeout=DEFAULT_TIMEOUT, model_version=MODEL_VERSION,
            language=None):
    """PDF -> MinerU -> <id>.md + images/。断点：batch_id 存 .mineru_state.json。

    返回 md 绝对路径。失败抛异常（由调用方落 failed）。
    """
    token = schema.mineru_token(root)
    if not token:
        raise RuntimeError("MinerU token not found (<root>/.mineru_token or MINERU_TOKEN)")
    pdir = schema.paper_dir(root, paper_id)
    pdf = os.path.join(pdir, f"{paper_id}.pdf")
    md = os.path.join(pdir, f"{paper_id}.md")
    if os.path.exists(md) and not os.path.exists(_state_path(pdir)):
        return md
    if not os.path.exists(pdf):
        raise RuntimeError(f"PDF not found: {pdf}")
    state = _load_state(pdir)

    if not state.get("batch_id"):
        payload = {"files": [{"name": os.path.basename(pdf), "data_id": paper_id}],
                   "model_version": model_version}
        if language:
            payload["language"] = language
        result = _http_json("POST", f"{API_BASE}/v4/file-urls/batch", token=token,
                            headers={"Content-Type": "application/json"}, json=payload)
        if result.get("code") != 0:
            raise RuntimeError(f"failed to request upload URL: {result.get('msg')}")
        state = {"batch_id": result["data"]["batch_id"],
                 "upload_url": result["data"]["file_urls"][0], "uploaded": False}
        _save_state(pdir, state)
        _log(f"{paper_id} batch_id={state['batch_id']}")

    if not state.get("uploaded"):
        with open(pdf, "rb") as f:
            resp = requests.put(state["upload_url"], data=f, timeout=600)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"upload failed HTTP {resp.status_code}: {resp.text[:200]}")
        state["uploaded"] = True
        _save_state(pdir, state)
        _log(f"{paper_id} uploaded")

    # 轮询
    start = time.time()
    while True:
        result = _http_json("GET", f"{API_BASE}/v4/extract-results/batch/{state['batch_id']}",
                            token=token)
        if result.get("code") != 0:
            raise RuntimeError(f"failed to query batch: {result.get('msg')}")
        items = {it["file_name"]: it for it in result["data"]["extract_result"]}
        item = items.get(os.path.basename(pdf))
        if item is None:
            raise RuntimeError("file not found in batch results")
        if item["state"] == "done":
            break
        if item["state"] == "failed":
            raise RuntimeError(f"MinerU parse failed: {item.get('err_msg', '')}")
        if time.time() - start > timeout:
            raise RuntimeError(f"poll timeout ({timeout}s), batch_id={state['batch_id']}; resume with retry")
        time.sleep(POLL_INTERVAL)

    # 下载 zip，解出 full.md 与 images/
    resp = requests.get(item["full_zip_url"], timeout=600)
    resp.raise_for_status()
    tmp_zip = os.path.join(pdir, ".result.zip")
    with open(tmp_zip, "wb") as f:
        f.write(resp.content)
    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            md_names = [n for n in zf.namelist() if os.path.basename(n) == "full.md"]
            if not md_names:
                raise RuntimeError("full.md not found in result zip")
            with zf.open(md_names[0]) as src, open(md, "wb") as dst:
                shutil.copyfileobj(src, dst)
            images = [n for n in zf.namelist() if n.startswith("images/") and not n.endswith("/")]
            for n in images:
                out = os.path.join(pdir, n)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with zf.open(n) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    finally:
        os.remove(tmp_zip)
    os.remove(_state_path(pdir))
    _log(f"{paper_id} markdown saved")
    return md
