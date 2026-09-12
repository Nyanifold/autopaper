#!/usr/bin/env bash
# autopaper data-root initializer.
# Usage: autopaper/init.sh [DIR | --root DIR]
#   Default root: $REFERENCE_WORKS if set, else ./reference-works under the current directory.
# Creates: <root>/_inbox/, <root>/_queue/input/, processed.csv, events.log, catalog.json, catalog.md
# Idempotent and non-destructive: existing files are kept as-is.
set -euo pipefail

case "${1:-}" in
  -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
  --root)    ROOT="${2:?--root requires a path}";;
  "")        ROOT="${REFERENCE_WORKS:-$PWD/reference-works}";;
  *)         ROOT="$1";;
esac

mkdir -p "$ROOT" "$ROOT/_inbox" "$ROOT/_queue/input"

# Keep in sync with CSV_FIELDS in scripts/schema.py; tests/test_init.py guards against drift.
CSV_HEADER='id,task_id,stage,md_sha256,pdf_sha256,summary_file,summary_hash,source,error,error_stage,created_at,updated_at'
[ -e "$ROOT/processed.csv" ] || printf '%s\n' "$CSV_HEADER" > "$ROOT/processed.csv"
[ -e "$ROOT/events.log" ]    || : > "$ROOT/events.log"
[ -e "$ROOT/catalog.json" ]  || printf '[]\n' > "$ROOT/catalog.json"
[ -e "$ROOT/catalog.md" ]    || printf '# Literature Catalog\n' > "$ROOT/catalog.md"

echo "data root: $ROOT"
echo "next: pick a MinerU backend (see MINERU.md), then submit e.g. 'autopaper/collect.sh --root $ROOT <arxiv-url>', or drop files into $ROOT/_inbox/"
