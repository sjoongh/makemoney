# trader/app/backfill_nasdaq_events.py
"""RESEARCH ONLY — backfill NASDAQ-100 8-K events into event_data/.

Orchestration only; every parsing/normalizing/storage piece is unit-tested
(tests/test_edgar_events.py, tests/test_event_store.py,
tests/test_index_universe.py). Rerunnable: the event store dedupes by
accession, and the universe membership snapshot is idempotent per date.

Usage:  python -m trader.app.backfill_nasdaq_events [--years 5]
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from trader.data.edgar import ticker_to_cik
from trader.data.edgar_events import fetch_submissions, normalize_edgar_events
from trader.data.event_store import save_events
from trader.data.index_universe import append_membership_snapshot, fetch_nasdaq100

logger = logging.getLogger(__name__)

EVENTS_PATH = Path("event_data/NASDAQ_events.parquet")
MEMBERSHIP_PATH = Path("universe_data/nasdaq100_membership.jsonl")
SEC_MIN_INTERVAL = 0.15  # stay far under SEC's 10 req/s

# company_tickers.json is missing some names (verified absent 2026-08-10);
# CIKs confirmed via the submissions API's own "tickers" field.
MANUAL_CIK_OVERRIDES = {"AEP": "0000004904"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=5)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=365 * args.years)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    constituents = fetch_nasdaq100()
    MEMBERSHIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    append_membership_snapshot(MEMBERSHIP_PATH, today, [s for s, _ in constituents])
    logger.info("universe: %d constituents (snapshot %s)", len(constituents), today)

    with httpx.Client(timeout=30.0) as client:
        cik_map = ticker_to_cik(client)

    all_rows: list[dict] = []
    missing: list[str] = []
    errors: list[str] = []
    for i, (ticker, _name) in enumerate(constituents):
        # company_tickers.json uses dotted class tickers (BRK.B), ours are dashed.
        cik = (
            cik_map.get(ticker)
            or cik_map.get(ticker.replace("-", "."))
            or MANUAL_CIK_OVERRIDES.get(ticker)
        )
        if cik is None:
            missing.append(ticker)
            continue
        try:
            rows = normalize_edgar_events(ticker, cik, fetch_submissions(cik))
        except Exception as exc:  # noqa: BLE001 — collected, reported, non-zero exit
            errors.append(f"{ticker}: {exc}")
            continue
        recent = [r for r in rows if r["filing_date"] >= cutoff]
        all_rows.extend(recent)
        if (i + 1) % 20 == 0:
            logger.info("%d/%d fetched (%d events so far)", i + 1, len(constituents), len(all_rows))
        time.sleep(SEC_MIN_INTERVAL)

    n = save_events(EVENTS_PATH, all_rows, created_ts=now.isoformat())
    logger.info("stored %d events → %s", n, EVENTS_PATH)
    if missing:
        logger.warning("no CIK for %d tickers: %s", len(missing), ",".join(missing))
    if errors:
        logger.error("fetch errors (%d): %s", len(errors), " | ".join(errors[:5]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
