# -*- coding: utf-8 -*-
"""sources.py DOI 反推 / Crossref PDF 回退单测（网络调用打桩）：python3 autopaper/tests/test_sources.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import sources


def test_doi_for_id():
    assert sources.doi_for_id("doi-10.1063-5.0287366") == "10.1063/5.0287366"
    assert sources.doi_for_id("chemrxiv.15003852") == "10.26434/chemrxiv.15003852"
    assert sources.doi_for_id("chemrxiv.15003852.v1") == "10.26434/chemrxiv.15003852.v1"
    assert sources.doi_for_id("2026.04.11.717183v1") == "10.1101/2026.04.11.717183v1"
    assert sources.doi_for_id("2504.08066") is None
    print("test_doi_for_id: OK")


def test_arxiv_raw_id():
    assert sources._arxiv_raw_id("2504.08066v2") == "2504.08066v2"
    assert sources._arxiv_raw_id("arxiv-cs-0701001") == "cs/0701001"
    assert sources._arxiv_raw_id("arxiv-hep-th-9901001") == "hep-th/9901001"
    assert sources._arxiv_raw_id("arxiv-math.gt-0309136") == "math.GT/0309136".lower()
    assert sources._arxiv_raw_id("repo-foo-bar") is None
    print("test_arxiv_raw_id: OK")


def test_find_pdf_url():
    orig = sources._crossref_message
    try:
        # 只认 content-type 含 pdf 的 link
        sources._crossref_message = lambda doi: {"link": [
            {"content-type": "text/xml", "URL": "https://x/y.xml"},
            {"content-type": "application/pdf", "URL": "https://x/y.pdf"}]}
        assert sources.find_pdf_url("doi-10.1234-abc") == "https://x/y.pdf"
        # 显式 DOI 优先，且可覆盖推不出的 id
        sources._crossref_message = lambda doi: {
            "link": [{"content-type": "application/pdf", "URL": "https://e/" + doi}]}
        assert sources.find_pdf_url("2504.08066", explicit_doi="10.1/x") == "https://e/10.1/x"
        # 推不出 DOI：不发起网络调用
        calls = []
        sources._crossref_message = lambda doi: calls.append(doi) or None
        assert sources.find_pdf_url("web-abc") is None and calls == []
        # 无 pdf link / Crossref 失败 → None
        sources._crossref_message = lambda doi: {"link": [{"content-type": "text/html", "URL": "https://x"}]}
        assert sources.find_pdf_url("doi-10.1234-abc") is None
        sources._crossref_message = lambda doi: None
        assert sources.find_pdf_url("doi-10.1234-abc") is None
    finally:
        sources._crossref_message = orig
    print("test_find_pdf_url: OK")


if __name__ == "__main__":
    test_doi_for_id()
    test_arxiv_raw_id()
    test_find_pdf_url()
    print("ALL OK")
