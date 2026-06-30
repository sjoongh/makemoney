#!/usr/bin/env bash
# Daily backup of the small, IRREPLACEABLE point-in-time forward data to git.
# (The bulky forward_data/*.parquet and fundamentals_edgar/ are re-fetchable and
#  stay gitignored; only the can't-reconstruct logs are committed here.)
set -euo pipefail
cd "$(dirname "$0")/.."

git add \
  forward_data/_fundamentals.jsonl \
  beta_paper_track.jsonl \
  research_data/_universe_log.jsonl \
  paper_forward/ 2>/dev/null || true

if git diff --cached --quiet; then
  echo "$(date '+%F %T') backup: nothing new"
  exit 0
fi

git commit -q -m "data: forward point-in-time backup $(date +%F)"
if git push -q origin HEAD 2>/dev/null; then
  echo "$(date '+%F %T') backup: committed + pushed"
else
  echo "$(date '+%F %T') backup: committed locally; push FAILED (will retry next run)"
fi
