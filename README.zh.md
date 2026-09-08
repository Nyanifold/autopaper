# autopaper —— 文献收集流水线

`autopaper` 把研究工作（论文 / 预印本 / 代码项目）收集进一个结构化、自动判重的文献库。每篇被投递的工作会被下载、转化为 Markdown（MinerU）、富化题录元信息并编入索引——全程确定性脚本，无 LLM、无人工门禁。总结是可选的解耦阶段，由 agent 按需执行。

本目录是**代码根**（脚本 + 提示词 + 文档，平铺）。数据在独立的**数据根**（默认 `references/reference-works/`），每条命令都可用 `--root` 指定。

## 快速上手

```bash
cd autopaper
python3 scripts/collect.py https://arxiv.org/abs/2504.08066 --repo SakanaAI/AI-Scientist-v2
```

`collect.py` 是一键命令：参数与 `add.py` 完全一致，受理后立即跑完全部流程（下载 → MinerU 转化 → 题录富化 → 索引刷新）直到 `done`，并打印产物路径。产物在 `<root>/2504.08066/`：

```
2504.08066/
├── 2504.08066.pdf      # 原始论文
├── 2504.08066.md       # MinerU 转化全文
├── images/             # md 引用的图片
├── AI-Scientist-v2/    # 克隆的代码仓库（保留 .git，commit 已锁定）
├── support/            # 附加材料（zip/tar 自动解压）
└── meta.json           # 规范元信息：题录、来源、sha256 等
```

准备：申请 MinerU API token——在 [mineru.net](https://mineru.net) 注册，API 文档见 <https://mineru.net/apiManage/docs>。token 写入 `<root>/.mineru_token`（权限 600），或设置环境变量 `MINERU_TOKEN`。

## 命令一览

所有命令在本目录以 `python3 scripts/<cmd>.py …` 运行，都接受 `--root <路径>`（或环境变量 `REFERENCE_WORKS`；默认 `references/reference-works/`）。

| 命令 | 用途 |
| --- | --- |
| `collect.py <source> [--repo …]* [--support …]*` | **一键**：投递 + 执行全部流程到 `done` |
| `add.py <source> [--repo …]* [--support …]* [--wait]` | 只投递+受理；打印 `task_id` |
| `add.py --inbox <name>.pdf […]` | 给 `_inbox/` 中已有的 PDF 补投元信息（repo/support） |
| `run.py [--until <stage>] [--from <stage>]` | worker：消费 `_inbox` + `_queue`，推进到 `done` |
| `status.py` | 查看流水与待办任务 |
| `retry.py [id…]` | 失败论文从失败阶段续跑 |
| `enrich.py [id…]` | 重抓题录 → `meta.json`（幂等） |
| `catalog.py` | 重新生成 `catalog.json` / `catalog.md`（幂等） |
| `support.py add <id> <url>` | 给已有文献追加附加材料 |

`<source>` 接受 arXiv URL、裸 arXiv id、其他 URL、本地路径（PDF 或 `.url`）。判重按 id 与 pdf sha256：重复投递返回 `duplicate` + 已有 `paper_id`（退出码 2），不重复干活。

### 关于来源的说明

- **优先用规范标识**：arXiv URL/id 与 DOI 能自动抓到完整题录。出版社页面 URL（如 `pubs.aip.org/…`）不含 DOI 且页面有反爬——会退化为 `web-<hash>` id、抓不到题录。只有这类 URL 时，先查它的 DOI（如用 [Crossref](https://search.crossref.org/)），改投 `https://doi.org/<doi>`。
- **付费墙或无法下载的 PDF**：手动下载后投本地路径（`collect.py … /path/to/paper.pdf`）或丢进 `_inbox/`。**文件名尽量用 DOI 命名**（如 `10.1063_5.0287366.pdf`，`/` 可写成 `_`）——这样 id 规则识别为 `doi-…`，enrich 能抓到题录；随意命名（`paper.pdf`）会退化为 `file-<hash>` id，没有元信息。也可以显式提供 DOI：`--doi 10.xxxx/…`（文件名不规范时优先用此法）。

### 投递盒

无需终端：把文件丢进 `<root>/_inbox/` 即可——`*.pdf`、`*.url` / `*.txt`（单行 URL 或 arXiv id）、或完整的任务 `*.json`（除 `task_id`/`source` 外字段全可选）。同主名的 `<name>.pdf` + `<name>.json` 视为一次投递（json 携带元信息）。下一次 `run.py`（手动或 cron 每 10–30 分钟）会认领并处理。

## 流水线与状态

```
registered → fetching → converting → enriching → (summarizing) → cataloging → done
```

- 论文级状态在 `<root>/processed.csv`（唯一事实源）；任务级回执在 `<root>/_queue/<task-id>.json`（`queued/running/done/duplicate/rejected`）；事件追加到 `<root>/events.log`。
- 任何中断：重跑同一命令即续传，不重复下载/解析。MinerU 转化失败可换 `vlm` 模型或拆页后用 `retry.py` 续跑。
- MinerU 限制：单文件 ≤200 页、每日优先页额度。批量时建议 `run.py --until converting` 分段跑。
- 若 PDF 无法下载（付费墙/链接失效）：手动下载后用本地路径投递，或丢进 `_inbox/`。

## 总结（可选，agent 驱动）

刻意**没有 `summarize.py`**。`summary.md`——中立、锚定到转化后 md 的总结——由 agent 按提示词契约 `prompts/summarize.zh.md` 现场产出。事实小节（题录/目录内容/仓库结构）从 `meta.json` + 目录扫描确定性组装，LLM 只写归纳部分。没有总结论文照样到 `done`；catalog 的摘要列待总结落地后自动补上。

## 目录结构

```
autopaper/
├── README.zh.md                 # 本文件
├── HINT.zh.md                   # 下游 AGENTS.md 用的最简导引
├── prompts/summarize.zh.md      # 总结提示词契约
└── scripts/                     # 全部命令 + 共享模块（平铺）；运行：python3 scripts/<cmd>.py
    ├── add.py collect.py run.py status.py retry.py enrich.py catalog.py support.py
    └── schema.py identity.py taskqueue.py registry.py sources.py fetch.py convert.py
```

模块规则：一个阶段一个模块；共享逻辑只放共享模块；纯判定函数（id 规则、查重、schema）无 IO、离线单测；命令脚本互不调用——唯一例外是 `collect.py`（add + run 的纯编排组合）。
