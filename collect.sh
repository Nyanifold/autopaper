#!/usr/bin/env bash
# autopaper one-shot entry point. Equivalent to `python3 autopaper/scripts/collect.py "$@"`.
# Run from any directory: `autopaper/collect.sh <source> [--repo …] [--support …] [--doi …]`
# Data root defaults to ./reference-works (relative to your cwd); override with --root.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/scripts/collect.py" "$@"
