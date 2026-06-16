"""trader/app/run_momentum.py — RESEARCH ONLY live momentum runner.

Usage:
    python -m trader.app.run_momentum [--years N]

Fetches OHLCV history for a fixed 15-name universe (10 US NASDAQ + 5 KR KOSPI),
runs the cross-sectional 12-1 momentum backtest, and prints the metrics table.

SURVIVORSHIP CAVEAT:
    This universe is hand-picked and NOT survivorship-free.  Results cannot
    be used as evidence of live edge.  See format_momentum_report() for full
    honest caveat.  For a credible research result you need a large,
    point-in-time construction universe with no look-ahead on inclusion.

Rate-limit handling:
    Yahoo Finance (NASDAQ symbols) throttles aggressive fetchers.
    We sleep ~1.5s between fetches.  On 429, we SKIP that symbol and continue.
    If <6 symbols fetched total, we still run on what's available and clearly
    note the data-limited universe.

Universe design (mix of winners + laggards to reduce winner-bias):
    US (NASDAQ): AAPL, MSFT, JNJ, KO, PG, WMT, INTC, CSCO, ORCL, GE
      — includes secular underperformers (INTC, GE) to reduce pure winner bias
    KR (KOSPI):  005930 (Samsung), 000660 (SK Hynix), 005380 (Hyundai Motor),
                  035420 (NAVER), 051910 (LG Chem)
"""
from __future__ import annotations

import argparse
import sys
import time
import logging

from trader.data.research_provider import ResearchDataProvider
from trader.core.events import Market, Symbol
from trader.research.momentum import cross_sectional_momentum, format_momentum_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Universe definition
# ---------------------------------------------------------------------------

# Mix of secular winners AND laggards to partially reduce winner-selection bias.
# Still survivorship-biased (all companies survived to today).  Disclosed below.
US_TICKERS = ["AAPL", "MSFT", "JNJ", "KO", "PG", "WMT", "INTC", "CSCO", "ORCL", "GE"]
KR_TICKERS = ["005930", "000660", "005380", "035420", "051910"]

MIN_SYMBOLS_TO_RUN = 6  # below this, note data-limited but still run

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-sectional momentum research backtest")
    parser.add_argument("--years", type=int, default=10, help="Years of history to fetch (default 10)")
    parser.add_argument("--refresh", action="store_true", help="Force re-fetch (bypass parquet cache)")
    args = parser.parse_args()

    print(f"\n{'='*72}")
    print(f"  UNIVERSE: {len(US_TICKERS)} US (NASDAQ) + {len(KR_TICKERS)} KR (KOSPI)  |  years={args.years}")
    print(f"{'='*72}\n")
    print("  SURVIVORSHIP NOTE: Universe is hand-picked; all names survived to today.")
    print("  Results are in-sample only.  See caveat in report below.\n")

    provider = ResearchDataProvider()

    bars_by_symbol: dict[str, list] = {}
    skipped_429:   list[str] = []
    skipped_other: list[str] = []
    fetched:       list[str] = []

    # --- Fetch US NASDAQ ---
    for ticker in US_TICKERS:
        log.info(f"Fetching NASDAQ:{ticker} ...")
        try:
            bars = provider.daily_history(ticker, "NASDAQ", years=args.years, refresh=args.refresh)
            if bars:
                bars_by_symbol[ticker] = bars
                fetched.append(f"NASDAQ:{ticker} ({len(bars)} bars)")
                log.info(f"  → {len(bars)} bars")
            else:
                log.warning(f"  → empty, skipping {ticker}")
                skipped_other.append(f"NASDAQ:{ticker} (empty response)")
        except RuntimeError as e:
            msg = str(e)
            if "429" in msg:
                log.warning(f"  → 429 rate-limit, skipping {ticker}")
                skipped_429.append(f"NASDAQ:{ticker}")
            else:
                log.warning(f"  → error ({msg[:80]}...), skipping {ticker}")
                skipped_other.append(f"NASDAQ:{ticker}")
        time.sleep(1.5)

    # --- Fetch KR KOSPI ---
    for ticker in KR_TICKERS:
        log.info(f"Fetching KOSPI:{ticker} ...")
        try:
            bars = provider.daily_history(ticker, "KOSPI", years=args.years, refresh=args.refresh)
            if bars:
                bars_by_symbol[ticker] = bars
                fetched.append(f"KOSPI:{ticker} ({len(bars)} bars)")
                log.info(f"  → {len(bars)} bars")
            else:
                log.warning(f"  → empty, skipping {ticker}")
                skipped_other.append(f"KOSPI:{ticker} (empty response)")
        except RuntimeError as e:
            msg = str(e)
            if "429" in msg:
                log.warning(f"  → 429 rate-limit, skipping {ticker}")
                skipped_429.append(f"KOSPI:{ticker}")
            else:
                log.warning(f"  → error ({msg[:80]}...), skipping {ticker}")
                skipped_other.append(f"KOSPI:{ticker}")
        time.sleep(0.5)

    # --- Report fetch results ---
    print(f"\n{'─'*72}")
    print(f"  FETCH RESULTS: {len(bars_by_symbol)} symbols fetched, "
          f"{len(skipped_429)} 429-skipped, {len(skipped_other)} other-skipped")
    print(f"{'─'*72}")
    for f in fetched:
        print(f"  ✓  {f}")
    for s in skipped_429:
        print(f"  ✗  {s}  [429 rate-limited — SKIPPED]")
    for s in skipped_other:
        print(f"  ✗  {s}  [error — SKIPPED]")

    if not bars_by_symbol:
        print("\n  ERROR: No symbols fetched. Check network / cache.")
        sys.exit(1)

    if len(bars_by_symbol) < MIN_SYMBOLS_TO_RUN:
        print(f"\n  WARNING: Only {len(bars_by_symbol)} symbols fetched (< {MIN_SYMBOLS_TO_RUN}).")
        print("  Universe is data-limited. Results should be treated with extra caution.\n")

    # --- Run backtest ---
    print(f"\n  Running backtest on {len(bars_by_symbol)} symbols ...\n")
    try:
        result = cross_sectional_momentum(
            bars_by_symbol,
            lookback=252,
            skip=21,
            top_pct=0.30,
            min_k=3,
            max_k=6,
            init_capital=10_000_000,
        )
    except ValueError as e:
        print(f"\n  ERROR running backtest: {e}")
        sys.exit(1)

    # --- Print report ---
    print(format_momentum_report(result))

    # --- Additional detail ---
    sm = result["strategy_metrics"]
    bm = result["benchmark_metrics"]
    log_entries = result["rebalance_log"]

    print(f"\n  Rebalances: {len(log_entries)}")
    print(f"  Strategy final equity: {sm.get('end_value', 0):,.0f}")
    print(f"  Benchmark final equity: {bm.get('end_value', 0):,.0f}")

    # Print last 3 rebalances for transparency
    if log_entries:
        print(f"\n  Last 3 rebalances:")
        for entry in log_entries[-3:]:
            print(f"    {entry['exec_date']}  strat={entry['strat_holdings']}  "
                  f"bench_n={len(entry['bench_holdings'])}  "
                  f"turnover={entry['strat_turnover']:.2%}")

    print()


if __name__ == "__main__":
    main()
