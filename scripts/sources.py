# -*- coding: utf-8 -*-
"""来源适配：arXiv / Crossref 题录抓取（§3.3）。网络 adapter 层。"""
import re
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "autopaper/0.1 (literature collector)"}
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def fetch_arxiv(arxiv_id):
    """arXiv API -> 题录 dict；失败返回 None。"""
    base = arxiv_id.split("v")[0]
    try:
        resp = requests.get(f"https://export.arxiv.org/api/query?id_list={arxiv_id}",
                            headers=UA, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    root = ET.fromstring(resp.text)
    entry = root.find(f"{ATOM}entry")
    if entry is None or entry.find(f"{ATOM}title") is None:
        return None
    title = re.sub(r"\s+", " ", entry.find(f"{ATOM}title").text or "").strip()
    authors = [a.find(f"{ATOM}name").text for a in entry.findall(f"{ATOM}author")]
    published = (entry.find(f"{ATOM}published").text or "")[:4]
    summary = re.sub(r"\s+", " ", entry.find(f"{ATOM}summary").text or "").strip()
    cats = [c.get("term") for c in entry.findall(f"{ATOM}category")]
    journal = entry.find(f"{ARXIV_NS}journal_ref")
    doi_el = entry.find(f"{ARXIV_NS}doi")
    venue = journal.text if journal is not None else f"arXiv:{base}" + (f" [{cats[0]}]" if cats else "")
    return {"title": title, "authors": authors,
            "year": int(published) if published.isdigit() else None,
            "venue": venue, "abstract": summary,
            "web": {"arxiv_abs": f"https://arxiv.org/abs/{base}",
                    "doi": doi_el.text if doi_el is not None else None}}


def fetch_crossref(doi):
    """Crossref -> 题录 dict；失败返回 None。"""
    try:
        resp = requests.get(f"https://api.crossref.org/works/{doi}",
                            headers=UA, timeout=30)
        if resp.status_code != 200:
            return None
        m = resp.json()["message"]
    except (requests.RequestException, ValueError, KeyError):
        return None
    authors = [" ".join(filter(None, [a.get("given"), a.get("family")]))
               for a in m.get("author", [])]
    year = None
    for key in ("published", "issued", "created"):
        parts = m.get(key, {}).get("date-parts", [[None]])
        if parts[0][0]:
            year = parts[0][0]
            break
    title = (m.get("title") or [""])[0]
    container = (m.get("container-title") or [""])[0]
    return {"title": title, "authors": authors, "year": year,
            "venue": container or f"doi:{doi}", "abstract": m.get("abstract", ""),
            "web": {"doi": f"https://doi.org/{doi}"}}


def fetch_biblio(paper_id):
    """按 id 形态选 adapter；抓不到返回 None（不猜测）。"""
    if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", paper_id):
        return fetch_arxiv(paper_id)
    if re.match(r"^\d{4}\.\d{2}\.\d{2}\.\d{4,7}(v\d+)?$", paper_id):
        return fetch_crossref(f"10.1101/{paper_id}")
    m = re.match(r"^chemrxiv\.(\d+)(?:\.v(\d+))?$", paper_id)
    if m:
        doi = f"10.26434/chemrxiv.{m.group(1)}" + (f".v{m.group(2)}" if m.group(2) else "")
        return fetch_crossref(doi)
    if paper_id.startswith("doi-"):
        return fetch_crossref(paper_id[4:].replace("-", "/", 1))
    return None
