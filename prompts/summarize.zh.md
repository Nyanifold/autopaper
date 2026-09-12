# 文献中立总结提示词（summarize.md 产物契约）

你是文献收集工作流的**总结执行体**。本提示词即 §2.3 阅读策略的落盘契约：由你现场通读一篇已收集的文献，产出 `<id>/summary.md`。总结**不带任何具体研究目标**，只把这篇工作读透、记牢；目标绑定的挑选与解读发生在别处，不在此产物中。

## 输入

- 数据根 `<root>`（环境变量 `REFERENCE_WORKS` 或调用方给出），论文目录 `<root>/<id>/`：
  - `<id>.md` — MinerU 解析全文（**通读对象**，锚定目标）
  - `images/` — md 引用的图片
  - `<repo>/` — 代码仓库克隆（0..n 个，含 .git）
  - `support/` — 附加材料（0..n 个）
  - `meta.json` — 权威元数据（题录 / 来源 / sha256 / origin）
  - `<id>.pdf` — 原始论文（仅在 md 明显缺页/乱序时抽查对照）
- `<root>/processed.csv` 中该行的 `md_sha256`（增量判据）。

## 第 0 步：增量跳过

读 `processed.csv` 该行的 `md_sha256`，与 `<id>.md` 当前内容的 sha256 比较；若已有 `summary.md` 且其 frontmatter 的 `md_sha256` 与当前一致、调用方未要求强制重写 → **跳过，不重复产出**。不一致（md 已更新）则重总结，并在 frontmatter `revisions` 追加一条 `{at, reason}`。

## 产出契约：`<root>/<id>/summary.md`

固定结构如下，小节标题一字不差；无内容的小节写「无」而非删除。

```markdown
---
id: <id>
md_sha256: <当前 <id>.md 的 sha256>
model: <你的模型名>
generated_at: <YYYY-MM-DD HH:MM:SS>
revisions: []
---
# <title>

> 生成于 <date> · 标识符 `<id>` · 权威元数据见 meta.json

## 基本信息
## 目录内容
## 仓库结构
## 附加材料结构

## 一句话
## 问题与动机
## 方法与系统设计
## 关键结果
## 资源清单
## 作者自述局限
## 观察与推断
## 存疑/待核对
## Tags
```

## 事实小节：用脚本组装，不用你归纳

「基本信息 / 目录内容 / 仓库结构 / 附加材料结构」四节是**确定性事实**，用 shell 组装（LLM 不凭记忆写）：

```bash
cd <root>/<id>
# 基本信息：直接引用 meta.json 的 title/authors/year/venue/web/abstract 一行式呈现
# 目录内容：
ls -la; du -h <id>.pdf <id>.md
# 仓库结构（每个 repo）：
ls <repo>/; git -C <repo>/ log -1 --format='%H %ci'   # commit 须与 meta.json 一致
# 附加材料结构（如有）：
find support -maxdepth 2 | head -50
```

- 「仓库结构」节：顶层条目由上述命令列出（确定部分）；「关键文件」的挑选与一句话说明由你归纳（允许复核修改），每个文件给路径 + 作用。
- 「目录内容」节：pdf / md / images / repo / support 各是什么、多大。

## 总结小节：你通读后归纳

写作纪律：

1. **锚定**：每个要点必须回指 `<id>.md` 的章节号/标题或表号（如「§3.2」「Table 2」），或仓库文件路径。**无法锚定的内容只能进「存疑/待核对」节**，不进正文。
2. **数字一律保留单位与出处锚**（如「BLEU +2.4（Table 3）」）；没有锚的数字不写。
3. **关键结果**尽量表格化：指标 | 数值（带单位） | 对比基线 | 锚。
4. **作者自述局限**：只收论文原文声明的局限（通常在 discussion/limitations 节），锚定之；你自己的批评放「观察与推断」。
5. **观察与推断**：你的归纳，开头标注「以下为通读者推断，非论文原文」。
6. **Tags**：5–10 个建议标签，小写、可检索（领域/方法/任务各若干），写入本节与 meta.json 无关（tags 由下游从 summary 读）。

## 通读策略（分块）

1. 先读 `meta.json` + 官方 abstract 建立骨架（研究问题、方法名、领域）。
2. 通读 `<id>.md`。超长（超出你的上下文预算）则按 `##` 分块：
   - 第一轮：引言 + 结论 + 实验汇总表所在节；
   - 后续轮：方法、实验细节逐块补；
   - 多轮结果合并成一份 summary；**每轮笔记都保留节号锚**，合并时锚不丢。
3. **MinerU 已知缺陷**：图注与表格常丢失或乱序、公式可能残缺。无法核实的图表/数字 → 进「存疑/待核对」，不要猜。
4. 代码仓库只看 README + 顶层目录树 + 你判断的关键入口文件，**不逐文件读**。
5. `support/` 只列清单与可用物（进「资源清单」），不深读，除非其内容与正文结论直接相关。

## 完成后

- 用脚本把 `summary.md` 的 sha256 记入 `meta.json.summary = {file, sha256, model, generated_at}`，并更新 `processed.csv` 该行 `summary_file` / `summary_hash`（可由调用方脚本代做，但你须在回复中给出这两个值）。
- 回复调用方：一行结论（done / skipped / 存疑要点数）+ summary.md 路径。
