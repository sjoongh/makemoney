# trader/app/run_reconcile.py
"""Reconciliation runner: load journal decisions, fetch fresh bars, write forward returns.

Usage:
    python -m trader.app.run_reconcile [--market KOSPI|NASDAQ|ALL] [--year 2026]

This script:
  1. Loads journal records from paper_forward/
  2. Fetches fresh daily bars via KIS (or loads from saved parquet if available)
  3. Calls reconcile() to compute forward returns at 1/5/20-day horizons
  4. Writes results to paper_forward/{engine}/{market}/{year}.reconciled.jsonl
  5. Prints a summary of per-source hit-rates at the 5-day horizon

HONEST CAVEAT: With a small number of reconciled records (N < 30), hit-rate estimates
are not statistically significant and should not be used for decisions.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
from collections import defaultdict
from datetime import date

from trader.live.journal import SignalJournal, reconcile

PAPER_FORWARD_ROOT = "paper_forward"
JOURNAL_ENGINE = "fusion_v1"


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip(); value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def _fetch_bars_via_kis(symbols: list) -> dict:
    """Fetch fresh bars from KIS. Returns dict: ticker → list[BarEvent]."""
    import httpx
    from trader.app.config import AppConfig
    from trader.execution.kis_client import KisClient

    PAPER_BASE = "https://openapivts.koreainvestment.com:29443"
    _load_dotenv()
    cfg = AppConfig.from_env()
    http = httpx.Client(base_url=PAPER_BASE, timeout=30)
    kis = KisClient(http, cfg.kis_app_key, cfg.kis_app_secret, cfg.kis_account,
                    paper=cfg.paper, min_interval=1.0)

    bars_by_symbol: dict = {}
    for ticker, market, currency in symbols:
        bars = kis.daily_bars(ticker, market, currency)
        bars_by_symbol[ticker] = sorted(bars, key=lambda b: b.ts)
    return bars_by_symbol


def _print_summary(reconciled: list) -> None:
    """Print per-source hit-rate at 5d horizon, with an honest caveat on small N."""
    source_hits: dict = defaultdict(list)
    for rec in reconciled:
        outcome = rec.get("outcome") or {}
        hit = outcome.get("hit_5d")
        for source in rec.get("source_scores", {}):
            if hit is not None:
                source_hits[source].append(hit)

    total = len(reconciled)
    reconciled_count = sum(
        1 for r in reconciled
        if (r.get("outcome") or {}).get("fwd_return_5d") is not None
    )

    print(f"\n=== Reconciliation Summary ===")
    print(f"Total records : {total}")
    print(f"Reconciled (5d available): {reconciled_count}")
    print()

    if not source_hits:
        print("No reconciled hit data available yet.")
        print("(Expected on day 1 — insufficient forward bars.)")
    else:
        print(f"{'Source':<30} {'N':>5}  {'Hit-rate 5d':>12}")
        print("-" * 50)
        for source, hits in sorted(source_hits.items()):
            n = len(hits)
            rate = sum(hits) / n if n else float("nan")
            print(f"{source:<30} {n:>5}  {rate:>12.1%}")

    print()
    print("CAVEAT: With small N (< 30), hit-rate estimates are not statistically")
    print("significant and should NOT be used for trading decisions.")


def main(market: str = "ALL", year: int = None) -> None:
    if year is None:
        year = date.today().year

    from trader.app.run_daily import SYMBOLS, filter_symbols_by_market
    symbols = filter_symbols_by_market(SYMBOLS, market)
    if not symbols:
        print(f"No symbols for market={market!r}. Exiting.")
        return

    journal = SignalJournal(root=PAPER_FORWARD_ROOT)

    # Collect all records across markets for the target year
    markets_in_symbols = {m for _, m, _ in symbols}
    all_records: list = []
    for mkt in sorted(markets_in_symbols):
        records = journal.load(JOURNAL_ENGINE, mkt, year)
        all_records.extend(records)

    print(f"Loaded {len(all_records)} decision record(s) for year={year}.")

    if not all_records:
        print("No journal records found. Run run_daily first to generate records.")
        return

    # Fetch fresh bars
    print("Fetching fresh bars for reconciliation …")
    try:
        bars_by_symbol = _fetch_bars_via_kis(symbols)
    except Exception as exc:
        print(f"Could not fetch bars: {exc}")
        print("Cannot reconcile without fresh bar data.")
        return

    # Reconcile
    reconciled = reconcile(all_records, bars_by_symbol, horizons=(1, 5, 20))

    # Write derived reconciled files (never overwrite source)
    root = pathlib.Path(PAPER_FORWARD_ROOT)
    for mkt in sorted(markets_in_symbols):
        mkt_records = [r for r in reconciled if r.get("market") == mkt]
        if not mkt_records:
            continue
        out_path = root / JOURNAL_ENGINE / mkt / f"{year}.reconciled.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as f:
            for row in mkt_records:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        print(f"Wrote {len(mkt_records)} reconciled record(s) → {out_path}")

    _print_summary(reconciled)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile paper-forward journal")
    parser.add_argument("--market", choices=["NASDAQ", "KOSPI", "ALL"], default="ALL")
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()
    main(market=args.market, year=args.year)
