# trader/app/run_evaluate.py
"""Real-data engine-validation evaluation runner.

Fetches live KIS daily bars for AAPL (NASDAQ) and 005930 (KOSPI), runs
evaluate() across a fixed threshold sensitivity grid, and prints format_report().

Usage:
    python -m trader.app.run_evaluate

DIAGNOSTIC ONLY — see format_report() disclaimer.  This is engine validation,
not a trading signal or strategy recommendation.
"""
from __future__ import annotations

import os
import tempfile

from trader.app.fetch_data import _load_dotenv, build_client, fetch
from trader.backtest.evaluate import evaluate, format_report
from trader.data.storage import load_bars

SYMBOLS = [
    ("AAPL", "NASDAQ", "USD"),
    ("005930", "KOSPI", "KRW"),
]

THRESHOLDS = (0.10, 0.20, 0.35)


def main() -> None:
    # Load credentials from .env if not already in environment
    if "KIS_APP_KEY" not in os.environ:
        _load_dotenv()

    print("Fetching real KIS daily bars ...")
    print(f"  Symbols : {SYMBOLS}")
    print(f"  Thresholds (fixed sensitivity grid): {THRESHOLDS}")
    print()

    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        out_path = tmp.name

    try:
        client = build_client()
        n = fetch(SYMBOLS, out_path, client=client, lookback_days=730)
        print(f"  Fetched {n} bars total -> {out_path}")
        print()

        bars = load_bars(out_path)

        # Show what we got per symbol
        by_sym: dict[str, list] = {}
        for b in bars:
            key = f"{b.symbol.ticker}[{b.symbol.market.value}]"
            by_sym.setdefault(key, []).append(b)
        for sym_label, sym_bars in sorted(by_sym.items()):
            sym_bars_s = sorted(sym_bars, key=lambda b: b.ts)
            print(
                f"  {sym_label:25s}: {len(sym_bars_s):3d} bars  "
                f"{sym_bars_s[0].ts.date()} → {sym_bars_s[-1].ts.date()}  "
                f"close {sym_bars_s[0].close:.2f} → {sym_bars_s[-1].close:.2f}"
            )
        print()

        result = evaluate(bars, thresholds=THRESHOLDS)
        report = format_report(result)
        print(report)

    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


if __name__ == "__main__":
    main()
