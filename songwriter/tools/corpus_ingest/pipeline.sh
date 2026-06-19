#!/usr/bin/env bash
# Full corpus pipeline: fetch → extract → aggregate → enrich_db
# Run from the repo root.
#
# Usage:
#   ./tools/corpus_ingest/pipeline.sh              # fetch all artists, apply all
#   ./tools/corpus_ingest/pipeline.sh --dry-run    # aggregate + dry-run enrich only
#   ./tools/corpus_ingest/pipeline.sh --skip-fetch # skip fetch, re-run everything else

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="$REPO_ROOT/.venv/bin/python"

DRY_RUN=false
SKIP_FETCH=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)   DRY_RUN=true ;;
    --skip-fetch) SKIP_FETCH=true ;;
  esac
done

cd "$REPO_ROOT"

if [ "$SKIP_FETCH" = false ]; then
  echo "=== STEP 1: Fetch lyrics (Genius) ==="
  $PYTHON -m tools.corpus_ingest.fetch --all-profiles --limit 10 --skip-existing
else
  echo "=== STEP 1: Fetch skipped ==="
fi

echo ""
echo "=== STEP 2: Extract per-song stats ==="
$PYTHON -m tools.corpus_ingest.extract

echo ""
echo "=== STEP 3: Aggregate (genre + artist vocab, cadence, clichés) ==="
$PYTHON -m tools.corpus_ingest.aggregate

echo ""
if [ "$DRY_RUN" = true ]; then
  echo "=== STEP 4: Enrich DB (dry-run) ==="
  $PYTHON -m tools.corpus_ingest.enrich_db
else
  echo "=== STEP 4: Enrich DB (apply) ==="
  $PYTHON -m tools.corpus_ingest.enrich_db --apply
fi

echo ""
echo "=== Pipeline complete ==="
