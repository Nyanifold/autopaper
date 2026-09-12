# -*- coding: utf-8 -*-
"""convert.py 后端选择 / schema 配置读取单测（无网络）：python3 autopaper/tests/test_convert.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import schema
import convert


def test_pick_mode():
    # 优先级：本地服务 > 本地命令 > 在线 API
    assert convert.pick_mode("http://127.0.0.1:8000", "mineru", "tok") == "service"
    assert convert.pick_mode(None, "mineru", "tok") == "command"
    assert convert.pick_mode(None, None, "tok") == "online"
    assert convert.pick_mode("", "", "") is None
    assert convert.pick_mode(None, None, None) is None
    print("test_pick_mode: OK")


def test_config_readers():
    for name in ("MINERU_URL", "MINERU_COMMAND", "MINERU_TOKEN"):
        os.environ.pop(name, None)
    root = schema.ensure_root(tempfile.mkdtemp(prefix="autopaper-conv-"))
    assert schema.mineru_url(root) is None
    assert schema.mineru_command(root) is None
    # 空 .mineru_command 文件 → 默认命令 mineru
    open(os.path.join(root, schema.MINERU_COMMAND_FILE), "w").close()
    assert schema.mineru_command(root) == "mineru"
    # 非空内容原样返回（可携带额外参数）
    with open(os.path.join(root, schema.MINERU_COMMAND_FILE), "w") as f:
        f.write("mineru -b pipeline -l en\n")
    assert schema.mineru_command(root) == "mineru -b pipeline -l en"
    # .mineru_url 去空白
    with open(os.path.join(root, schema.MINERU_URL_FILE), "w") as f:
        f.write("http://127.0.0.1:8000\n")
    assert schema.mineru_url(root) == "http://127.0.0.1:8000"
    print("test_config_readers: OK")


if __name__ == "__main__":
    test_pick_mode()
    test_config_readers()
    print("ALL OK")
