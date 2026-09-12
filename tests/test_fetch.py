# -*- coding: utf-8 -*-
"""fetch.py 下载重试 / PDF 校验 / .part 清理单测（网络调用打桩）：python3 autopaper/tests/test_fetch.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import fetch


def test_assert_pdf():
    d = tempfile.mkdtemp(prefix="autopaper-fetch-")
    p = os.path.join(d, "a.pdf")
    with open(p, "wb") as f:
        f.write(b"%PDF-1.7\n...")
    fetch.assert_pdf(p)
    with open(p, "wb") as f:
        f.write(b"<html>not a pdf</html>")
    try:
        fetch.assert_pdf(p)
        raise AssertionError("html should be rejected")
    except RuntimeError:
        pass
    print("test_assert_pdf: OK")


def test_download_retry_and_cleanup():
    d = tempfile.mkdtemp(prefix="autopaper-fetch-")
    dest = os.path.join(d, "x.pdf")
    orig_once, orig_sleep = fetch._download_once, fetch.time.sleep
    fetch.time.sleep = lambda s: None  # 测试不真等
    try:
        calls = {"n": 0}

        def flaky(url, tmp, headers):
            calls["n"] += 1
            if calls["n"] < 3:
                raise fetch.requests.ConnectionError("boom")
            with open(tmp, "wb") as f:
                f.write(b"%PDF-1.4 ok")

        fetch._download_once = flaky
        assert fetch.download("https://x/y.pdf", dest, attempts=3) == dest
        assert calls["n"] == 3
        assert open(dest, "rb").read().startswith(b"%PDF-")
        assert not os.path.exists(dest + ".part")

        def always_fail(url, tmp, headers):
            with open(tmp, "wb") as f:
                f.write(b"partial")
            raise fetch.requests.ConnectionError("nope")

        fetch._download_once = always_fail
        try:
            fetch.download("https://x/y.pdf", dest + "2", attempts=2)
            raise AssertionError("should fail")
        except RuntimeError:
            pass
        assert not os.path.exists(dest + "2.part"), ".part must be cleaned on failure"
    finally:
        fetch._download_once, fetch.time.sleep = orig_once, orig_sleep
    print("test_download_retry_and_cleanup: OK")


if __name__ == "__main__":
    test_assert_pdf()
    test_download_retry_and_cleanup()
    print("ALL OK")
