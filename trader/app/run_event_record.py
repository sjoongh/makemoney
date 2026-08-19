# trader/app/run_event_record.py
"""RESEARCH ONLY — daily incremental disclosure-event recorder (cron).

Free-data expansion Phase 6. Appends the trailing window of KOSPI (DART) and
NASDAQ (EDGAR) events into event_data/; the event store dedupes on merge so
overlapping windows are safe to re-run.

Dead-man's switch: heartbeat "event_record" is recorded only when the run is
not a total failure, gated on ERROR FRACTION (a weekend with zero new filings
is legitimately empty — 0 rows must NOT look unhealthy, an all-corps outage
must). Same discipline as run_forward_record.

Usage:  python -m trader.app.run_event_record [--days 7]
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from trader.app.backfill_kospi_events import DART_MIN_INTERVAL, _load_env_key
from trader.app.backfill_nasdaq_events import (
    MANUAL_CIK_OVERRIDES,
    MEMBERSHIP_PATH,
    SEC_MIN_INTERVAL,
)
from trader.data.dart import DartBudget, fetch_corp_codes, fetch_list_page, normalize_dart_events
from trader.data.edgar import ticker_to_cik
from trader.data.edgar_events import fetch_submissions, normalize_edgar_events
from trader.data.event_store import save_events
from trader.data.index_universe import append_membership_snapshot, fetch_nasdaq100
from trader.data.kospi_universe import KOSPI_TOP200
from trader.live import heartbeat as hb

logger = logging.getLogger(__name__)

KOSPI_PATH = Path("event_data/KOSPI_events.parquet")
NASDAQ_PATH = Path("event_data/NASDAQ_events.parquet")
BUDGET_PATH = Path("event_data/.dart_budget.json")


def record_kospi(days: int, now: datetime) -> tuple[int, int, int]:
    """Fetch trailing-window DART events; returns (attempted, errors, rows)."""
    api_key = _load_env_key()
    budget = DartBudget(BUDGET_PATH)
    today = now.strftime("%Y-%m-%d")
    bgn = (now - timedelta(days=days)).strftime("%Y%m%d")
    end = now.strftime("%Y%m%d")
    if not budget.try_spend(today):
        return len(KOSPI_TOP200), len(KOSPI_TOP200), 0
    corp_map = fetch_corp_codes(api_key)
    rows: list[dict] = []
    errors = 0
    for symbol in KOSPI_TOP200:
        corp = corp_map.get(symbol)
        if corp is None or not budget.try_spend(today):
            errors += 1
            continue
        try:
            recs, _ = fetch_list_page(api_key, corp, bgn, end)
            rows.extend(normalize_dart_events(recs, market="KOSPI"))
        except Exception as exc:  # noqa: BLE001 — counted, gates heartbeat
            errors += 1
            logger.warning("DART %s: %s", symbol, exc)
        time.sleep(DART_MIN_INTERVAL)
    if rows:
        save_events(KOSPI_PATH, rows, created_ts=now.isoformat())
    return len(KOSPI_TOP200), errors, len(rows)


def record_nasdaq(days: int, now: datetime) -> tuple[int, int, int]:
    """Fetch trailing-window EDGAR events; returns (attempted, errors, rows)."""
    cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    constituents = fetch_nasdaq100()
    append_membership_snapshot(
        MEMBERSHIP_PATH, now.strftime("%Y-%m-%d"), [s for s, _ in constituents]
    )
    with httpx.Client(timeout=30.0) as client:
        cik_map = ticker_to_cik(client)
    rows: list[dict] = []
    errors = 0
    for ticker, _name in constituents:
        cik = (
            cik_map.get(ticker)
            or cik_map.get(ticker.replace("-", "."))
            or MANUAL_CIK_OVERRIDES.get(ticker)
        )
        if cik is None:
            errors += 1
            continue
        try:
            all_rows = normalize_edgar_events(ticker, cik, fetch_submissions(cik))
            rows.extend(r for r in all_rows if r["filing_date"] >= cutoff)
        except Exception as exc:  # noqa: BLE001 — counted, gates heartbeat
            errors += 1
            logger.warning("EDGAR %s: %s", ticker, exc)
        time.sleep(SEC_MIN_INTERVAL)
    if rows:
        save_events(NASDAQ_PATH, rows, created_ts=now.isoformat())
    return len(constituents), errors, len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    now = datetime.now(timezone.utc)

    k_n, k_err, k_rows = record_kospi(args.days, now)
    n_n, n_err, n_rows = record_nasdaq(args.days, now)
    logger.info("KOSPI: %d/%d ok, %d rows | NASDAQ: %d/%d ok, %d rows",
                k_n - k_err, k_n, k_rows, n_n - n_err, n_n, n_rows)

    # Heartbeat gated on error fraction, not row count (weekend zero is fine).
    attempted = k_n + n_n
    errors = k_err + n_err
    if attempted > 0 and errors >= attempted:
        logger.error("every source errored — NOT recording heartbeat")
        return 1
    hb.record("event_record", ts=now.isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
