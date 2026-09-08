# HINT: reference-works/ —— 已收集的文献，可直接读

本目录包含为项目收集的工作（论文 / 预印本 / 代码项目），**可能与你的任务相关**。每篇论文都**已转化为 Markdown**——直接读全文即可，无需解析 PDF。

## 目录组织

```
reference-works/
├── catalog.md             # 全库人读总览表（从这里开始）
├── catalog.json           # 同一索引的机器可读版（id/标题/年份/tags/状态）
├── processed.csv          # 处理流水（流水线状态，一般与你无关）
├── _inbox/  _queue/       # 投递盒与任务队列（用于新增文献）
├── events.log             # 追加式事件日志
└── <id>/                  # 每篇工作一个目录，如 2504.08066/
    ├── <id>.md            # Markdown 全文（MinerU 转化）——读这个
    ├── <id>.pdf           # 原始 PDF
    ├── images/            # md 引用的图片
    ├── meta.json          # 规范元数据：标题/作者/摘要/链接/哈希
    ├── summary.md         # 中立总结（带锚定；已总结过才有）
    ├── <repo>/            # 克隆的代码仓库（如有；commit 固定在 meta.json）
    └── support/           # 附加材料（如有）
```

## 怎么用

- **挑候选**：浏览 `catalog.md`（或按 tags 过滤 `catalog.json`）。
- **读一篇**：有 `summary.md` 先读它（30 秒事实页 + 带锚定的总结）；否则读 `meta.json` 的摘要，再读 `<id>/<id>.md` 全文。图在 `<id>/images/`。
- **用代码**：`<id>/<repo>/` 是完整 git 克隆，版本固定在 meta.json 记录的 commit。
- **精确引用**：总结中的要点锚定到 `<id>.md` 的章节/表号，引用时优先用这些锚。

## 新增一篇（可选）

命令在 `autopaper/scripts/`（从 `autopaper/` 下以 `python3 scripts/<cmd>.py` 运行），都接受 `--root <本目录>`：

```bash
python3 scripts/collect.py --root <reference-works> <arxiv-url|pdf路径> [--repo owner/repo]
python3 scripts/add.py     --root <reference-works> <source>   # 只投递，稍后跑
python3 scripts/run.py     --root <reference-works>            # 处理待办任务
python3 scripts/status.py  --root <reference-works>            # 查看流水线状态
```

也可以直接把 PDF 或 `.url` 文件（单行 URL 或 arXiv id）丢进 `_inbox/`，下次 `run.py` 时自动处理。重复投递会被自动判重——重投同一篇不会重复干活，只返回已有 id。

注意：MinerU 转化可能丢失或打乱图注与表格；关键数字请对照 PDF 核实。

**如果 PDF 下载失败**（付费墙、链接失效、网络限制——任务会在 fetching 阶段以 `rejected`/`failed` 告终）：不要盲目重试。请用户手动下载 PDF 并把文件交给你，然后用本地路径投递——`collect.py --root <reference-works> /path/to/paper.pdf`，或直接把文件丢进 `_inbox/`。若知道它的 DOI，用 `--doi 10.xxxx/…` 显式提供——这样得到规范的 `doi-…` id 并能抓到完整元信息，而不是退化为 `file-<hash>`。
