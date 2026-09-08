# autopaper — literature collection pipeline

`autopaper` collects research works (papers / preprints / code projects) into a structured, deduplicated library. Each submitted work is downloaded, converted to Markdown (via MinerU), enriched with bibliographic metadata, and indexed — a fully deterministic script pipeline with no LLM and no human gate. Summarization is an optional, decoupled stage carried out by an agent on demand.

This directory is the **code root** (scripts + prompts + docs, flat layout). Data lives in a separate **data root** (default `references/reference-works/`), selectable per command with `--root`.

## Quick start

```bash
cd autopaper
python3 scripts/collect.py https://arxiv.org/abs/2504.08066 --repo SakanaAI/AI-Scientist-v2
```

`collect.py` is the one-shot command: it takes exactly the same arguments as `add.py`, then runs the whole pipeline (fetch → MinerU convert → enrich → catalog) until `done` and prints the artifact path. Results land in `<root>/2504.08066/`:

```
2504.08066/
├── 2504.08066.pdf      # original paper
├── 2504.08066.md       # full text, MinerU conversion
├── images/             # figures referenced by the md
├── AI-Scientist-v2/    # cloned repository (.git kept, commit pinned)
├── support/            # supplementary material (zip/tar auto-extracted)
└── meta.json           # canonical metadata: bibliography, sources, sha256, …
```

Prerequisite: a MinerU API token — register at [mineru.net](https://mineru.net) and see the API docs at <https://mineru.net/apiManage/docs>. Put the token in `<root>/.mineru_token` (chmod 600), or export `MINERU_TOKEN`.

## Commands

All commands run from this directory as `python3 scripts/<cmd>.py …` and accept `--root <path>` (or env `REFERENCE_WORKS`; default `references/reference-works/`).

| Command | Purpose |
| --- | --- |
| `collect.py <source> [--repo …]* [--support …]*` | **One-shot**: submit + run everything to `done` |
| `add.py <source> [--repo …]* [--support …]* [--wait]` | Submit + register only; prints `task_id` |
| `add.py --inbox <name>.pdf […]` | Attach metadata (repo/support) to a PDF already in `_inbox/` |
| `run.py [--until <stage>] [--from <stage>]` | Worker: drain `_inbox` + `_queue`, drive tasks to `done` |
| `status.py` | Show the ledger and open tasks |
| `retry.py [id…]` | Resume failed papers from the failing stage |
| `enrich.py [id…]` | (Re)fetch bibliography → `meta.json` (idempotent) |
| `catalog.py` | Regenerate `catalog.json` / `catalog.md` (idempotent) |
| `support.py add <id> <url>` | Add supplementary material to an existing work |

`<source>` accepts an arXiv URL, a bare arXiv id, another URL, or a local path (PDF or `.url`). Duplicates are detected by id and pdf sha256: resubmitting returns `duplicate` + the existing `paper_id` (exit code 2) without redoing any work.

### Notes on sources

- **Prefer canonical identifiers**: arXiv URLs/ids and DOIs fetch full metadata automatically. Publisher page URLs (e.g. `pubs.aip.org/…`) contain no DOI and their pages block bots — they fall back to a `web-<hash>` id with no bibliography. If you only have such a URL, look up its DOI first (e.g. via [Crossref](https://search.crossref.org/)) and submit `https://doi.org/<doi>` instead.
- **Paywalled or undownloadable PDFs**: download the PDF manually and submit the local path (`collect.py … /path/to/paper.pdf`) or drop it into `_inbox/`. **Name the file after its DOI** (e.g. `10.1063_5.0287366.pdf`; `/` may be written as `_`) so the id rule recognizes it as `doi-…` and enrich can fetch the bibliography — a generic filename (`paper.pdf`) falls back to a `file-<hash>` id with no metadata. Alternatively, pass the DOI explicitly with `--doi 10.xxxx/…` (preferred when the filename is not DOI-shaped).

### Drop-box submission

No terminal needed: drop files into `<root>/_inbox/` — a `*.pdf`, a `*.url` / `*.txt` (single line: URL or arXiv id), or a full task `*.json` (all fields optional except `task_id`/`source`). A `<name>.pdf` + `<name>.json` pair counts as one submission (the json carries the metadata). The next `run.py` (manual or cron every 10–30 min) claims and processes them.

## Pipeline and states

```
registered → fetching → converting → enriching → (summarizing) → cataloging → done
```

- Paper-level state lives in `<root>/processed.csv` (the single source of truth); task-level receipts in `<root>/_queue/<task-id>.json` (`queued/running/done/duplicate/rejected`); everything is appended to `<root>/events.log`.
- Any interruption: rerun the same command to resume — nothing is downloaded or parsed twice. If MinerU conversion fails, `retry.py` resumes, optionally after switching to the `vlm` model or splitting pages.
- MinerU limits: ≤200 pages per file, daily priority-page quota. For batches, run `run.py --until converting` in stages.

## Summarization (optional, agent-driven)

There is intentionally **no `summarize.py`**. A `summary.md` — neutral, anchored to the converted md — is produced on demand by an agent following the prompt contract `prompts/summarize.md`. Facts sections (bibliography / directory contents / repo structure) are assembled deterministically from `meta.json` + directory scans; the LLM only writes the inductive parts. Works reach `done` without a summary; the catalog's summary column is filled in once summaries exist.

## Repository layout

```
autopaper/
├── README.md                    # this file
├── HINT.md                      # minimal reader for downstream AGENTS.md
├── prompts/summarize.md         # summarization prompt contract
├── tests/                       # unit tests (local only, not uploaded; run: python3 tests/test_identity.py)
└── scripts/                     # all commands + shared modules, flat; run: python3 scripts/<cmd>.py
    ├── add.py collect.py run.py status.py retry.py enrich.py catalog.py support.py
    └── schema.py identity.py taskqueue.py registry.py sources.py fetch.py convert.py
```

Module rules: one stage = one module; shared logic lives in the shared modules only; pure decision functions (id rules, dedup, schema) are IO-free and unit-tested offline; command scripts never call each other — except `collect.py`, the single sanctioned composition of add + run.

