# autopaper — literature collection pipeline

`autopaper` collects research works (papers / preprints / code projects) into a structured, deduplicated library. Each submitted work is downloaded, converted to Markdown (via MinerU), enriched with bibliographic metadata, and indexed — a fully deterministic script pipeline with no LLM and no human gate. Summarization is an optional, decoupled stage carried out by an agent on demand.

This directory is the **code root** (scripts + prompts + docs, flat layout). Data lives in a separate **data root** (default `./reference-works/`, i.e. under the directory where you run the command), selectable per command with `--root`.

## Quick start

### 0. Prerequisite: a MinerU conversion backend

autopaper converts PDFs to Markdown through MinerU. Configure a backend in the data root (`<root>/`); if several are present, the higher-priority one wins:

| Priority | Config in `<root>/` | Env | Backend |
| --- | --- | --- | --- |
| 1 | `.mineru_url` | `MINERU_URL` | Local/remote `mineru-api` service, e.g. `http://127.0.0.1:8000` — no token needed |
| 2 | `.mineru_command` | `MINERU_COMMAND` | Local `mineru` CLI (installed on this machine); file content is the command, an empty file means `mineru` |
| 3 | `.mineru_token` | `MINERU_TOKEN` | Online [MinerU](https://mineru.net) API — register, see <https://mineru.net/apiManage/docs>, chmod 600 |

- **Local service** — start `mineru-api` (defaults to `127.0.0.1:8000`), then point autopaper at it: `echo http://127.0.0.1:8000 > <root>/.mineru_url`. Self-hosted `mineru-api` needs no token. Backend and OCR language default to `hybrid-engine` / `ch`; override with `MINERU_BACKEND` / `MINERU_LANG`.
- **Local command** — with `mineru` on `PATH`, just create the file: `touch <root>/.mineru_command`. autopaper runs `<command> -p <paper>.pdf -o <tmp>` and collects the Markdown + `images/`. Put any flags you need in the file (e.g. `mineru -b pipeline` on a CPU-only box). Models must be present locally (`mineru-models-download`).
- **Online** — the fallback: token in `<root>/.mineru_token` (chmod 600) or `MINERU_TOKEN`.

Do this before anything else — without a working backend the pipeline stalls at the conversion stage. To install MinerU from scratch — models, a `mineru-api` service, or the CLI — see [`MINERU.md`](MINERU.md).

### 1. Clone and run from your project directory

The data root defaults to `./reference-works/` relative to **where you run the command**, so run it from your project's directory (no `cd` into `autopaper`):

```bash
cd /path/to/your-project
git clone https://github.com/Nyanifold/autopaper.git .            # or clone elsewhere and reference the path below
pip install -r autopaper/requirements.txt                          # runtime dependency: requests
autopaper/collect.sh https://arxiv.org/abs/2504.08066 --repo SakanaAI/AI-Scientist-v2
```

This creates `./reference-works/` under your project directory, and the result lands in `./reference-works/2504.08066/`:

```
reference-works/2504.08066/
├── 2504.08066.pdf      # original paper
├── 2504.08066.md       # full text, MinerU conversion
├── images/             # figures referenced by the md
├── AI-Scientist-v2/    # cloned repository (.git kept, commit pinned)
├── support/            # supplementary material (zip/tar auto-extracted)
└── meta.json           # canonical metadata: bibliography, sources, sha256, …
```

`collect.py` is the one-shot command: it takes exactly the same arguments as `add.py`, then runs the whole pipeline (fetch → MinerU convert → enrich → catalog) until `done` and prints the artifact path.

Shortcut: `autopaper/collect.sh` is a thin shell wrapper for the same command — run `autopaper/collect.sh <source> [--repo …] [--support …] [--doi …]` from any directory (bash/zsh).

To create the data root up front, run `autopaper/init.sh` — it builds `./reference-works/` (or the directory you pass as its argument) with the expected `_inbox/`, `_queue/`, ledger and catalog files. It is idempotent and never overwrites existing data.

## Commands

All commands run from your project directory as `python3 autopaper/scripts/<cmd>.py …` and accept `--root <path>` (or env `REFERENCE_WORKS`; default `./reference-works/` under the current directory). `init.sh` and `collect.sh` are shell entry points run directly.

| Command | Purpose |
| --- | --- |
| `init.sh [DIR]` | Create the expected data-root structure (idempotent, never overwrites); default `./reference-works/` |
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

- **Prefer canonical identifiers**: arXiv URLs/ids and `https://doi.org/<doi>` URLs fetch full metadata automatically. Publisher page URLs (e.g. `pubs.aip.org/…`) contain no DOI and block bots — they get a `web-<hash>` id, and the fetching stage fails because no PDF address can be derived. If you only have such a URL, look up its DOI first (e.g. via [Crossref](https://search.crossref.org/)) and submit `https://doi.org/<doi>` instead.
- **What downloads automatically**: arXiv (incl. old-style `cs/0701001`), bioRxiv / medRxiv, and any URL ending in `.pdf`. For `doi-…` ids and chemRxiv, fetch derives a DOI and asks Crossref for a PDF link — best-effort, and fetching fails if Crossref has none. Downloads retry 3×, reject non-PDF responses, and can be size-capped with `AUTOPAPER_MAX_PDF_BYTES`.
- **Paywalled or undownloadable PDFs**: download the PDF manually and submit the local path (`collect.py … /path/to/paper.pdf`) or drop it into `_inbox/`. **Name the file after its DOI** (e.g. `10.1063_5.0287366.pdf`; `/` may be written as `_`) so the id rule recognizes it as `doi-…` and enrich can fetch the bibliography — a generic filename (`paper.pdf`) falls back to a `file-<hash>` id with no metadata. Alternatively, pass the DOI explicitly with `--doi 10.xxxx/…` (preferred when the filename is not DOI-shaped).

### Drop-box submission

No terminal needed: drop files into `<root>/_inbox/` — a `*.pdf`, a `*.url` / `*.txt` (single line: URL or arXiv id), or a full task `*.json` (all fields optional except `task_id`/`source`). A `<name>.pdf` + `<name>.json` pair counts as one submission (the json carries the metadata). The next `run.py` (manual or cron every 10–30 min) claims and processes them.

## Pipeline and states

```
registered → fetching → converting → enriching → (summarizing) → cataloging → done
```

- Paper-level state lives in `<root>/processed.csv` (the single source of truth); task-level receipts in `<root>/_queue/<task-id>.json` (`queued/running/done/duplicate/rejected`); everything is appended to `<root>/events.log`.
- Any interruption: rerun the same command to resume — nothing is downloaded or parsed twice. If MinerU conversion fails, `retry.py` resumes from the failing stage; to switch the online MinerU model set `MINERU_MODEL_VERSION` (default `vlm`) before retrying.
- MinerU limits: ≤200 pages per file, daily priority-page quota. For batches, run `run.py --until converting` in stages.

## Summarization (optional, agent-driven)

There is intentionally **no `summarize.py`**. A `summary.md` — neutral, anchored to the converted md — is produced on demand by an agent following the prompt contract `prompts/summarize.md`. Facts sections (bibliography / directory contents / repo structure) are assembled deterministically from `meta.json` + directory scans; the LLM only writes the inductive parts. Works reach `done` without a summary. `catalog.py` reads any `<id>/summary.md` it finds: it fills the catalog's `summary` column, takes `tags` from the summary's `## Tags` section (falling back to `meta.json`), and records `summary_file` / `summary_hash` in `processed.csv`. Re-run `catalog.py` after producing a summary.

## Reusing the library in another task

`HINT.md` (English) / `HINT.zh.md` (中文) is a minimal reader for whatever agent consumes the collected works. In a larger or more complex task, copy its content into the consuming project's `AGENTS.md` (or an equivalent global instruction), so that agent knows the library layout and how to read and cite works. The HINT only describes how to read the data root; it assumes the `autopaper/` code root stays available for adding new works.

## Repository layout

```
autopaper/
├── README.md                    # this file
├── HINT.md                      # minimal reader for downstream AGENTS.md
├── MINERU.md                    # how to install/run local MinerU (command or service)
├── requirements.txt             # runtime dependency: requests
├── prompts/summarize.md         # summarization prompt contract
├── tests/                       # offline unit tests; run: python3 tests/test_<module>.py
├── collect.sh                   # one-shot shortcut: autopaper/collect.sh …（bash/zsh）
├── init.sh                      # data-root initializer: autopaper/init.sh [DIR]（bash/zsh）
└── scripts/                     # all commands + shared modules, flat; run: python3 scripts/<cmd>.py
    ├── add.py collect.py run.py status.py retry.py enrich.py catalog.py support.py
    └── schema.py identity.py taskqueue.py registry.py sources.py fetch.py convert.py
```

Module rules: one stage = one module; shared logic lives in the shared modules only; pure decision functions (id rules, dedup, schema) are IO-free and unit-tested offline; command scripts never call each other — except `collect.py`, the single sanctioned composition of add + run.

