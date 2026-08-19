# trader/app/backfill_kr_flows.py
"""RESEARCH ONLY — backfill KOSPI-200 investor flows from Naver into flow_data/.

Orchestration only; parsing/store are unit-tested (tests/test_naver_flows.py).
Resumable: per-symbol progress ledger; the flow store dedupes by
(symbol, date) so reruns are safe. Politeness delay between requests.

Usage:  python -m trader.app.backfill_kr_flows [--years 5]
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from trader.data.kospi_universe import KOSPI_TOP200
from trader.data.naver_flows import fetch_frgn_page, save_flows

logger = logging.getLogger(__name__)

FLOWS_PATH = Path("flow_data/KOSPI_flows.parquet")
PROGRESS_PATH = Path("flow_data/.kr_flows_progress.json")
MIN_INTERVAL = 0.25
MAX_PAGES = 400  # hard stop per symbol (~16y) — backstop, never expected


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=5)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=365 * args.years)).strftime("%Y-%m-%d")

    done: set[str] = set()
    if PROGRESS_PATH.exists():
        done = set(json.loads(PROGRESS_PATH.read_text()))
        logger.info("resuming: %d/%d symbols done", len(done), len(KOSPI_TOP200))

    errors: list[str] = []
    todo = [s for s in KOSPI_TOP200 if s not in done]
    for i, symbol in enumerate(todo):
        rows: list[dict] = []
        try:
            for page in range(1, MAX_PAGES + 1):
                for attempt in range(3):
                    try:
                        page_rows = fetch_frgn_page(symbol, page)
                        break
                    except Exception as exc:  # noqa: BLE001 — retried, then raised
                        if attempt == 2:
                            raise
                        logger.warning("retry %s p%d: %s", symbol, page, exc)
                        time.sleep(2.0 * (attempt + 1))
                time.sleep(MIN_INTERVAL)
                if not page_rows:
                    break  # past the end of history
                rows.extend(r for r in page_rows if r["date"] >= cutoff)
                if page_rows[-1]["date"] < cutoff:
                    break
        except Exception as exc:  # noqa: BLE001 — isolate per symbol
            errors.append(f"{symbol}: {exc}")
            continue
        if rows:
            save_flows(
                FLOWS_PATH,
                [dict(r, symbol=symbol) for r in rows],
                created_ts=now.isoformat(),
            )
        done.add(symbol)
        PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROGRESS_PATH.write_text(json.dumps(sorted(done)))
        if (i + 1) % 10 == 0:
            logger.info("%d/%d symbols done", len(done), len(KOSPI_TOP200))

    logger.info("finished: %d/%d symbols → %s", len(done), len(KOSPI_TOP200), FLOWS_PATH)
    if errors:
        logger.error("symbol errors (%d): %s", len(errors), " | ".join(errors[:5]))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
