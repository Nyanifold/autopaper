# -*- coding: utf-8 -*-
"""identity.py 纯函数单测：python3 autopaper/tests/test_identity.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import identity

idn = identity.identify

# 规则 1：arXiv（裸 id / abs / pdf URL / 文件名；vN 保留）
assert idn({"type": "arxiv_id", "value": "2504.08066"}) == "2504.08066"
assert idn({"type": "url", "value": "https://arxiv.org/abs/2504.08066"}) == "2504.08066"
assert idn({"type": "url", "value": "https://arxiv.org/pdf/2504.08066v2"}) == "2504.08066v2"
assert idn({"type": "pdf_path", "value": "/tmp/2505.15047.pdf"}, content_sha="x") == "2505.15047"
assert identity.classify("2504.08066")["type"] == "arxiv_id"

# 规则 2：bioRxiv（文件名 / URL；/ 与 _ 等价）
assert idn({"type": "pdf_path", "value": "2026.04.11.717183v1.pdf"}, content_sha="x") == "2026.04.11.717183v1"
assert idn({"type": "url", "value": "https://www.biorxiv.org/content/10.1101/2026.04.11.717183v1"}) == "2026.04.11.717183v1"

# 规则 3：chemRxiv（_v -> .v）
assert idn({"type": "pdf_path", "value": "chemrxiv.15003852_v1.pdf"}, content_sha="x") == "chemrxiv.15003852.v1"
assert idn({"type": "pdf_path", "value": "chemrxiv.15003852.v1.pdf"}, content_sha="x") == "chemrxiv.15003852.v1"
assert idn({"type": "pdf_path", "value": "chemrxiv.15003852.pdf"}, content_sha="x") == "chemrxiv.15003852"

# 规则 4：其他 DOI
assert idn({"type": "url", "value": "https://doi.org/10.48550/arXiv.2504.08066"}) == "doi-10.48550-arxiv.2504.08066"

# 规则 5：GitHub（仅确无论文时）
assert idn({"type": "url", "value": "https://github.com/SakanaAI/AI-Scientist-v2"}) == "repo-sakanaai-ai-scientist-v2"
assert idn({"type": "repo_only", "value": "SakanaAI/AI-Scientist-v2"}) == "repo-sakanaai-ai-scientist-v2"
assert idn({"type": "repo_only", "value": "https://github.com/SakanaAI/AI-Scientist-v2.git"}) == "repo-sakanaai-ai-scientist-v2"

# 规则 6：本地 PDF 哈希回退（文件名未命中 1–5 时）
sha = "3f8a9c21d0b4" + "0" * 52
assert idn({"type": "pdf_path", "value": "paper-utils/randomblob"}, content_sha=sha) == "file-3f8a9c21d0b4"
assert idn({"type": "pdf_path", "value": "/tmp/随便什么名字.pdf"}, content_sha=sha) == "file-3f8a9c21d0b4"
# 但无扩展名、形如 arXiv id 的文件名仍按规则 1（文件名是最强提示）
assert idn({"type": "pdf_path", "value": "paper-utils/2505.15047"}, content_sha=sha) == "2505.15047"

# 规则 7：无法识别网页（规范化 URL 哈希：utm/尾斜杠/大小写不影响）
a = idn({"type": "url", "value": "https://Example.com/page/?utm_source=x"})
b = idn({"type": "url", "value": "http://example.com/page"})
assert a == b and a.startswith("web-") and len(a) == 16

# 规则 8：兜底
assert idn({"type": "unknown", "value": "Some Weird String"}).startswith("misc-")

# 版本号 = 不同文献
assert idn({"type": "arxiv_id", "value": "2504.08066"}) != idn({"type": "arxiv_id", "value": "2504.08066v2"})

# 确定性
assert idn({"type": "url", "value": "https://arxiv.org/abs/2504.08066"}) == \
       idn({"type": "url", "value": "https://arxiv.org/abs/2504.08066"})

# pdf_url_for
assert identity.pdf_url_for({"type": "arxiv_id", "value": "2504.08066"}, "2504.08066") == \
    "https://arxiv.org/pdf/2504.08066"
assert identity.pdf_url_for({"type": "url", "value": "https://x.org/a.pdf"}, "web-x") == "https://x.org/a.pdf"


# 显式 DOI 优先于文件名识别与哈希回退
assert idn({"type": "pdf_path", "value": "/tmp/2505.15047.pdf"}, content_sha=sha,
           doi="10.1063/5.0287366") == "doi-10.1063-5.0287366"
assert idn({"type": "pdf_path", "value": "/tmp/随便.pdf"}, content_sha=sha,
           doi="10.1063/5.0287366") == "doi-10.1063-5.0287366"
assert idn({"type": "url", "value": "https://example.com/x"}, doi="10.1063/ABC.DEF") == "doi-10.1063-abc.def"
assert identity.doi_id(" 10.1101/2026.04.11.717183 ") == "doi-10.1101-2026.04.11.717183"

# resolve：一次拿到 (id, 下载地址)
assert identity.resolve({"type": "arxiv_id", "value": "2504.08066"}) == \
    ("2504.08066", "https://arxiv.org/pdf/2504.08066")
_web_id = identity.identify({"type": "url", "value": "https://example.com/x"})
assert identity.resolve({"type": "url", "value": "https://example.com/x"}) == (_web_id, None)

# 规则表：默认顺序即判定优先级
assert [r.name for r in identity.RULES] == \
    ["arxiv", "generic-pdf", "biorxiv", "chemrxiv", "doi", "github"]

# 扩展性：新增一条规则即同时接通 id 与下载（无需改 identify/pdf_url_for）
def _demo_stem(stem):
    return "demo-1" if stem == "demo-paper" else None


def _demo_pdf(source, paper_id):
    return "https://demo.example/1.pdf" if paper_id == "demo-1" else None


_demo_rule = identity.SourceRule("demo", stem_id=_demo_stem, pdf_url=_demo_pdf)
identity.RULES.append(_demo_rule)
try:
    assert idn({"type": "pdf_path", "value": "/tmp/demo-paper.pdf"}, content_sha=sha) == "demo-1"
    assert identity.pdf_url_for({"type": "url", "value": "https://demo.example/x"}, "demo-1") == \
        "https://demo.example/1.pdf"
    assert identity.resolve({"type": "pdf_path", "value": "/tmp/demo-paper.pdf"},
                            content_sha=sha) == ("demo-1", "https://demo.example/1.pdf")
finally:
    identity.RULES.remove(_demo_rule)
assert idn({"type": "pdf_path", "value": "/tmp/demo-paper.pdf"}, content_sha=sha) == "file-3f8a9c21d0b4"

# 旧式 arXiv id：paper id 路径安全，下载地址保留原始 archive/num
assert identity.classify("cs/0701001")["type"] == "arxiv_id"
assert idn({"type": "arxiv_id", "value": "cs/0701001"}) == "arxiv-cs-0701001"
assert idn({"type": "arxiv_id", "value": "math.GT/0309136"}) == "arxiv-math.gt-0309136"
assert idn({"type": "url", "value": "https://arxiv.org/abs/cs/0701001"}) == "arxiv-cs-0701001"
assert identity.pdf_url_for({"type": "arxiv_id", "value": "cs/0701001"},
                            "arxiv-cs-0701001") == "https://arxiv.org/pdf/cs/0701001"
assert identity.pdf_url_for({"type": "url", "value": "https://arxiv.org/abs/cs/0701001"},
                            "arxiv-cs-0701001") == "https://arxiv.org/pdf/cs/0701001"
assert identity.pdf_url_for({"type": "arxiv_id", "value": "2504.08066"},
                            "2504.08066") == "https://arxiv.org/pdf/2504.08066"

# medRxiv 下载走 medRxiv 域名（不是 biorxiv）
assert identity.pdf_url_for(
    {"type": "url", "value": "https://www.medrxiv.org/content/10.1101/2026.04.11.717183v1"},
    "2026.04.11.717183v1") == \
    "https://www.medrxiv.org/content/10.1101/2026.04.11.717183v1.full.pdf"

# arXiv DOI 可直接推 PDF
assert idn({"type": "url", "value": "https://doi.org/10.48550/arXiv.2504.08066"}) == \
    "doi-10.48550-arxiv.2504.08066"
assert identity.pdf_url_for({"type": "url", "value": "https://doi.org/10.48550/arXiv.2504.08066"},
                            "doi-10.48550-arxiv.2504.08066") == "https://arxiv.org/pdf/2504.08066"

print("test_identity: OK")
