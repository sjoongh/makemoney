# trader/app/backfill_kospi_events.py
"""RESEARCH ONLY — backfill KOSPI-200 (top-200) DART disclosures into event_data/.

Orchestration only; parsing/normalizing/storage/budget are unit-tested
(tests/test_dart_events.py, tests/test_event_store.py). Resumable: a progress
ledger records which corps are done, the DartBudget caps requests below the
20k/day key limit, and the event store dedupes on merge — rerun anytime.

Universe = trader.data.kospi_universe.KOSPI_TOP200 (the repo's baked KR
universe; survivorship-biased like all current-constituent lists — see
docs/data-limitations.md).

Usage:  python -m trader.app.backfill_kospi_events [--years 5]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trader.data.dart import (
    DartBudget,
    fetch_corp_codes,
    fetch_list_page,
    normalize_dart_events,
)
from trader.data.event_store import save_events
from trader.data.kospi_universe import KOSPI_TOP200

logger = logging.getLogger(__name__)

EVENTS_PATH = Path("event_data/KOSPI_events.parquet")
PROGRESS_PATH = Path("event_data/.kospi_backfill_progress.json")
BUDGET_PATH = Path("event_data/.dart_budget.json")
DART_MIN_INTERVAL = 0.12


def _load_env_key() -> str:
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key and Path(".env").exists():
        for line in Path(".env").read_text().splitlines():
            if line.startswith("DART_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("DART_API_KEY not set (env or .env)")
    return key


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=5)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    api_key = _load_env_key()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    bgn_de = (now - timedelta(days=365 * args.years)).strftime("%Y%m%d")
    end_de = now.strftime("%Y%m%d")

    budget = DartBudget(BUDGET_PATH)
    done: set[str] = set()
    if PROGRESS_PATH.exists():
        done = set(json.loads(PROGRESS_PATH.read_text()))
        logger.info("resuming: %d/%d corps already done", len(done), len(KOSPI_TOP200))

    if not budget.try_spend(today):
        logger.error("DART budget exhausted for %s", today)
        return 1
    corp_map = fetch_corp_codes(api_key)

    def fetch_page_with_retry(corp: str, page: int) -> tuple[list[dict], int]:
        # DART flakes with transient ConnectTimeouts on long runs; 3x backoff.
        for attempt in range(3):
            try:
                return fetch_list_page(api_key, corp, bgn_de, end_de, page_no=page)
            except Exception as exc:  # noqa: BLE001 — last attempt re-raises
                if attempt == 2:
                    raise
                logger.warning("retry %d for corp %s p%d: %s", attempt + 1, corp, page, exc)
                time.sleep(2.0 * (attempt + 1))
        raise AssertionError("unreachable")

    def checkpoint(rows: list[dict]) -> None:
        if rows:
            save_events(EVENTS_PATH, rows, created_ts=now.isoformat())
        PROGRESS_PATH.write_text(json.dumps(sorted(done)))

    pending: list[dict] = []
    errors: list[str] = []
    stopped = False
    missing = [s for s in KOSPI_TOP200 if s not in corp_map]
    todo = [s for s in KOSPI_TOP200 if s in corp_map and s not in done]
    for i, symbol in enumerate(todo):
        corp = corp_map[symbol]
        page = 1
        try:
            while True:
                if not budget.try_spend(today):
                    logger.warning("budget cap hit — stopping (resumable)")
                    stopped = True
                    break
                recs, total_pages = fetch_page_with_retry(corp, page)
                pending.extend(normalize_dart_events(recs, market="KOSPI"))
                time.sleep(DART_MIN_INTERVAL)
                if page >= total_pages:
                    break
                page += 1
        except Exception as exc:  # noqa: BLE001 — isolate per corp, keep going
            errors.append(f"{symbol}: {exc}")
            continue
        if stopped:
            break
        done.add(symbol)
        if (i + 1) % 25 == 0:
            checkpoint(pending)
            pending = []
            logger.info(
                "%d/%d corps checkpointed (budget spent %d)",
                len(done), len(KOSPI_TOP200), budget.spent(today),
            )

    checkpoint(pending)
    logger.info("done: %d/%d corps → %s", len(done), len(KOSPI_TOP200), EVENTS_PATH)
    if errors:
        logger.error("corp errors (%d): %s", len(errors), " | ".join(errors[:5]))
    if missing:
        logger.warning("no corp_code for %d symbols: %s", len(missing), ",".join(missing))
    return 0 if len(done) == len(KOSPI_TOP200) - len(missing) else 1


if __name__ == "__main__":
    raise SystemExit(main())
