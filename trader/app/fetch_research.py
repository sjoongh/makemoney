# trader/app/fetch_research.py
"""RESEARCH ONLY — Fetch deep daily OHLCV history from Yahoo Finance (keyless).

This script is strictly for offline research / strategy evaluation.
It does NOT use KIS or any API key.  Live trading always uses fetch_data.py
(KIS-backed).  Never import this module from run_daily, run_paper, or any
live/parity path.

Usage:
    python -m trader.app.fetch_research <out.parquet> [TICKER:MARKET ...]

    TICKER : Exchange ticker, e.g. "AAPL" or "005930"
    MARKET : "NASDAQ" or "KOSPI"

Examples:
    # Fetch 10 years of AAPL (NASDAQ) daily bars
    python -m trader.app.fetch_research research_data/aapl.parquet AAPL:NASDAQ

    # Fetch Samsung Electronics (KOSPI) — symbol mapped to 005930.KS on Yahoo
    python -m trader.app.fetch_research research_data/samsung.parquet 005930:KOSPI

    # Multiple symbols into one file
    python -m trader.app.fetch_research research_data/universe.parquet AAPL:NASDAQ 005930:KOSPI

Data quality notes:
  - Yahoo adjusted-close is applied to O/H/L/C (split + dividend adjusted).
  - Volume is raw (unadjusted).
  - Yahoo may have gaps on holidays; downstream code should handle missing dates.
  - Results are cached in research_data/{MARKET}_{TICKER}.parquet per symbol.
    Re-run with --refresh to force a network fetch even if cache exists.
  - If Yahoo returns 429 (rate-limit), wait a few minutes and retry.

RESEARCH ONLY — NEVER use for live or paper trading signals.
"""
from __future__ import annotations

import sys

from trader.data.research_provider import ResearchDataProvider
from trader.data.storage import save_bars


def fetch_research(
    symbol_specs: list[tuple[str, str]],
    out_path: str,
    *,
    years: int = 10,
    cache_dir: str = "research_data",
    refresh: bool = False,
) -> int:
    """Fetch research bars for *symbol_specs* and save merged parquet to *out_path*.

    Args:
        symbol_specs: List of (ticker, market) pairs.
        out_path:     Destination parquet file path.
        years:        Years of history to request per symbol (default 10).
        cache_dir:    Directory for per-symbol parquet caches.
        refresh:      Force re-fetch from Yahoo even if cache exists.

    Returns:
        Total number of bars saved.

    Note:
        RESEARCH ONLY — never call from live/paper trading paths.
    """
    provider = ResearchDataProvider(cache_dir=cache_dir)
    all_bars = []
    for ticker, market in symbol_specs:
        bars = provider.daily_history(
            ticker, market, years=years, refresh=refresh
        )
        print(
            f"  {market}:{ticker} — {len(bars)} bars  "
            f"[{bars[0].ts.date()} → {bars[-1].ts.date()}]" if bars else f"  {market}:{ticker} — 0 bars"
        )
        all_bars.extend(bars)

    save_bars(all_bars, out_path)
    print(f"Saved {len(all_bars)} total bars → {out_path}")
    return len(all_bars)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="[RESEARCH ONLY] Fetch deep Yahoo OHLCV history, no API key required."
    )
    parser.add_argument("out", help="Output parquet path")
    parser.add_argument(
        "symbols",
        nargs="*",
        default=["AAPL:NASDAQ"],
        help="One or more TICKER:MARKET (e.g. AAPL:NASDAQ 005930:KOSPI)",
    )
    parser.add_argument("--years", type=int, default=10, help="Years of history (default 10)")
    parser.add_argument("--cache-dir", default="research_data", help="Cache directory")
    parser.add_argument(
        "--refresh", action="store_true", help="Force re-fetch even if cache exists"
    )
    args = parser.parse_args()

    specs = []
    for s in args.symbols:
        parts = s.split(":")
        if len(parts) != 2:
            print(f"ERROR: expected TICKER:MARKET, got {s!r}", file=sys.stderr)
            sys.exit(1)
        specs.append((parts[0], parts[1]))

    print("[RESEARCH ONLY] Fetching deep history via Yahoo Finance (keyless)...")
    n = fetch_research(specs, args.out, years=args.years, cache_dir=args.cache_dir, refresh=args.refresh)
    print(f"Done. {n} bars total.")
