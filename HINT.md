# HINT: reference-works/ — collected literature, ready to read

This directory contains works collected for this project (papers, preprints, code projects) that **may be relevant to your task**. Every paper has already been **converted to Markdown** — you can read the full text directly, no PDF parsing needed.

## Layout

```
reference-works/
├── catalog.md             # human-readable overview table of all works (start here)
├── catalog.json           # same index, machine-readable (id/title/year/tags/stage)
├── processed.csv          # processing ledger (pipeline state; usually not your concern)
├── _inbox/  _queue/       # submission drop box and task queue (for adding works)
├── events.log             # append-only event log
└── <id>/                  # one directory per work, e.g. 2504.08066/
    ├── <id>.md            # full text in Markdown (MinerU conversion) — read this
    ├── <id>.pdf           # original PDF
    ├── images/            # figures referenced by the md
    ├── meta.json          # canonical metadata: title/authors/abstract/links/hashes
    ├── summary.md         # neutral summary with section anchors (present if summarized)
    ├── <repo>/            # cloned code repository, if any (commit pinned in meta.json)
    └── support/           # supplementary material, if any
```

## How to use

- **Pick candidates**: skim `catalog.md` (or filter `catalog.json` by tags).
- **Read a work**: open `<id>/summary.md` first if it exists (30-second facts + anchored summary); otherwise read `<id>/meta.json` for the abstract, then `<id>/<id>.md` for full text. Figures are in `<id>/images/`.
- **Use the code**: each cloned repo under `<id>/<repo>/` is a full git clone at the commit recorded in `meta.json`.
- **Cite precisely**: summaries anchor claims to sections/tables of `<id>.md`; prefer quoting those anchors.

## Add a new work (optional)

Commands live in `autopaper/` (this repo). The most common entry is the one-shot wrapper, runnable from anywhere (bash/zsh); all commands accept `--root <this directory>`:

```bash
autopaper/collect.sh --root <reference-works> <arxiv-url|pdf-path> [--repo owner/repo] [--doi …]
autopaper/collect.sh --root <reference-works> --inbox <name>.pdf [--repo …]   # metadata for a PDF in _inbox
autopaper/scripts/add.py  --root <reference-works> <source>   # submit only, run later
autopaper/scripts/run.py  --root <reference-works>            # process pending tasks
autopaper/scripts/status.py --root <reference-works>          # pipeline status
```

Or simply drop a PDF / a `.url` file (one URL or arXiv id per line) into `_inbox/`; it will be processed on the next `run.py`. Duplicates are detected automatically — re-submitting an existing work is a no-op that returns the existing id.

Note: figure captions and tables may be lost or out of order in the MinerU conversion; when a number matters, cross-check the PDF.

**If the PDF download fails** (paywall, broken link, network restrictions — the task will end as `rejected`/`failed` at the fetching stage): do not retry blindly. Ask the user to download the PDF manually and hand you the file, then submit the local path instead — `autopaper/collect.sh --root <reference-works> /path/to/paper.pdf` or drop the file into `_inbox/`. If you know its DOI, pass it explicitly (`--doi 10.xxxx/…`) so the paper gets a canonical `doi-…` id and full metadata instead of a `file-<hash>` fallback.
