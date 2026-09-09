#!/bin/bash
# The weekly loop in one command: sync LegiScan, read new bills' text, fold the
# scores in, replay decisions, export, commit, push (the GitHub Action then
# redeploys the public map). Safe to re-run; each step is idempotent.
#
#   ./publish.sh              # full loop
#   ./publish.sh --no-sync    # skip the LegiScan calls (just re-export + push)
#   ./publish.sh --dry-run    # everything except commit + push
set -euo pipefail
cd "$(dirname "$0")"

SYNC=1; PUSH=1
for a in "$@"; do
  case "$a" in
    --no-sync) SYNC=0 ;;
    --dry-run) PUSH=0 ;;
    *) echo "unknown option: $a"; exit 2 ;;
  esac
done

[ -d backend/venv ] || { echo "No backend/venv -- run ./setup.sh first"; exit 1; }
source backend/venv/bin/activate
cd backend

if [ "$SYNC" = 1 ]; then
  python -m app.sync.legiscan_sync --all
  python -m app.sync.legiscan_sync --all --score-text
fi
python -m app.sync.legiscan_sync --all --rescore
python -m app.seed
python -m app.export
cd ..

if [ "$PUSH" = 1 ]; then
  if git diff --quiet -- docs/data.json backend/data; then
    echo "Nothing changed; nothing to publish."
  else
    git add docs/data.json backend/data
    git commit -m "Publish: sync $(date +%Y-%m-%d)"
    git push
    echo "Pushed. The map redeploys in about a minute."
  fi
else
  echo "Dry run: not committing. git status:"; git status --short
fi
