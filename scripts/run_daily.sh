#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
MARKET="${1:-ALL}"
MODE="${2:-}"   # pass --live to trade
mkdir -p logs
ts=$(date +%Y%m%d)
./.venv/bin/python -m trader.app.run_daily --market "$MARKET" $MODE >> "logs/run_daily_${MARKET}_${ts}.log" 2>&1
