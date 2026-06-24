# trader/app/accumulate_data.py
"""RESEARCH ONLY — Daily historical-data accumulator CLI.

Builds a local Parquet dataset of daily OHLCV bars for a broad universe
(US S&P 500 + KR KOSPI large-caps) in small daily batches, WITHOUT hitting
Yahoo Finance 429 rate limits.

DESIGN PHILOSOPHY:
  US history now comes from yfinance (curl_cffi browser impersonation), which
  no longer 429s, and KOSPI from Naver (permissive).  So the whole universe can
  be backfilled in a single run — pass a large --per-run (e.g. 300).  The
  resumable manifest still lets you stop/restart safely, and a daily cron keeps
  the dataset fresh as new bars print.

SURVIVORSHIP BIAS CAVEAT:
  The S&P 500 constituent list and KOSPI large-cap list reflect *current*
  membership.  Symbols that were removed (delisted, merged, reclassified)
  before today are absent.  This data is suitable only for exploratory
  research; it is NOT suitable for point-in-time backtests without further
  historical membership correction.

NEVER import or call this module from live/paper trading or the
backtest/live parity path.

Usage:
    python -m trader.app.accumulate_data [--per-run N] [--us-limit M]

Examples:
    # Default: fetch next 25 S&P500 symbols (top 120) + all KOSPI large-caps
    python -m trader.app.accumulate_data

    # Quick smoke-test: fetch next 4 symbols from a 8-symbol US universe
    python -m trader.app.accumulate_data --per-run 4 --us-limit 8
"""
from __future__ import annotations

import argparse
import sys

from trader.data.accumulator import DataAccumulator
from trader.data.research_provider import ResearchDataProvider
from trader.data.universe import universe


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "[RESEARCH ONLY] Resumable historical-data accumulator. "
            "Fetches the next batch of un-done symbols from S&P500+KOSPI "
            "universe and stores Parquet caches in research_data/. "
            "Run daily via cron; takes ~25 s per symbol."
        )
    )
    parser.add_argument(
        "--per-run",
        type=int,
        default=60,
        metavar="N",
        help="Symbols to fetch per cron run (default 60). yfinance (US) no "
             "longer 429s, so larger batches are fine; pass a big value (e.g. "
             "300) to backfill the whole universe in one go.",
    )
    parser.add_argument(
        "--us-limit",
        type=int,
        default=503,
        metavar="M",
        help="Max S&P 500 symbols in universe (default 503 = all).",
    )
    parser.add_argument(
        "--kr-limit",
        type=int,
        default=200,
        metavar="M",
        help="Max KOSPI symbols in universe (default 200, top by market cap).",
    )
    parser.add_argument(
        "--no-kr",
        action="store_true",
        help="Exclude KOSPI names from the universe.",
    )
    parser.add_argument(
        "--manifest",
        default="research_data/_manifest.json",
        help="Path to the JSON manifest (default research_data/_manifest.json).",
    )
    parser.add_argument(
        "--sleep-secs",
        type=float,
        default=1.0,
        help="Seconds to sleep between symbol fetches (default 1.0 — a "
             "research-only courtesy; yfinance/Naver no longer need 25 s).",
    )
    args = parser.parse_args(argv)

    print("=" * 60)
    print("[RESEARCH ONLY] Historical-data accumulator")
    print(
        "SURVIVORSHIP BIAS CAVEAT: S&P500 and KOSPI lists reflect "
        "current membership only — not suitable for point-in-time backtests."
    )
    print("=" * 60)

    print(f"\nBuilding universe (us_limit={args.us_limit}, kr={not args.no_kr})…")
    uni = universe(us_limit=args.us_limit, kr=not args.no_kr, kr_limit=args.kr_limit)
    print(f"  Universe size: {len(uni)} symbols")

    provider = ResearchDataProvider()
    acc = DataAccumulator(
        provider=provider,
        universe_list=uni,
        manifest_path=args.manifest,
        per_run=args.per_run,
        sleep_secs=args.sleep_secs,
    )

    targets = acc.select_next()
    print(f"\nSelected {len(targets)} symbol(s) this run (per_run={args.per_run}):")
    for ticker, market in targets:
        print(f"  {market}:{ticker}")

    if not targets:
        prog = acc.progress()
        print(
            f"\nNothing to fetch — {prog['done']}/{prog['total']} symbols done, "
            f"{prog['cooldown']} in cooldown."
        )
        _print_progress(acc)
        return

    print(f"\nFetching… (sleeping {args.sleep_secs}s between symbols)\n")
    summary = acc.run_once()

    print("\n" + "-" * 40)
    print("Run summary:")
    print(f"  Fetched:           {summary['fetched']}")
    print(f"  Cooled (429):      {summary['cooled']}")
    print(f"  Errored:           {summary['errored']}")
    print(f"  Remaining pending: {summary['remaining_pending']}")

    _print_progress(acc)

    if summary["cooled"] > 0:
        print(
            "\nWARNING: a source rate-limited (429) — rare now that US uses "
            "yfinance. Affected symbols placed in 24-hour cooldown; re-run "
            "later and the accumulator will resume automatically."
        )


def _print_progress(acc: DataAccumulator) -> None:
    prog = acc.progress()
    total = prog["total"]
    done = prog["done"]
    pct = 100 * done // total if total else 0
    print(
        f"\nManifest progress: {done}/{total} done ({pct}%) | "
        f"pending={prog['pending']} | "
        f"cooldown={prog['cooldown']} | "
        f"error={prog['error']}"
    )


if __name__ == "__main__":
    main()
