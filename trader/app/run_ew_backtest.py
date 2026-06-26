# trader/app/run_ew_backtest.py
"""RESEARCH ONLY — clean equal-weight backtest on the local dataset, per market.

Reports the momentum strategy vs the equal-weight basket benchmark, SINGLE
CURRENCY per market (US in USD, KR in KRW — never mixed).

⚠️ This is a FULL-SAMPLE, IN-SAMPLE, SURVIVORSHIP-BIASED diagnostic. A positive
strategy result here is NOT edge — the universe is today's survivors and the
period is in-sample. The split-disciplined IC harness (run_signal_zoo) is the
honest verdict, and it found no edge. Read docs/RESEARCH_CONCLUSION.md.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import argparse
import glob
import os

from trader.data.storage import load_bars
from trader.research.ew_backtest import run_ew_backtest


def _load(prefix: str, data_dir: str) -> dict[str, list]:
    out: dict[str, list] = {}
    for path in glob.glob(os.path.join(data_dir, f"{prefix}_*.parquet")):
        bars = load_bars(path)
        if bars:
            out[os.path.basename(path).replace(".parquet", "")] = bars
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="[RESEARCH ONLY] clean EW backtest, per market")
    p.add_argument("--data-dir", default="research_data")
    p.add_argument("--top-pct", type=float, default=0.10)
    p.add_argument("--max-k", type=int, default=20)
    args = p.parse_args(argv)

    print("=" * 72)
    print("[RESEARCH ONLY] Equal-weight momentum backtest — per market, single currency")
    print("  ⚠️  FULL-SAMPLE / IN-SAMPLE / SURVIVORSHIP-BIASED — not evidence of edge.")
    print("  The split-disciplined IC harness is the honest verdict (no edge).")
    print("=" * 72)

    for label, prefix in [("US (USD)", "NASDAQ"), ("KR (KRW)", "KOSPI")]:
        panel = _load(prefix, args.data_dir)
        if not panel:
            print(f"\n{label}: no data")
            continue
        r = run_ew_backtest(panel, top_pct=args.top_pct, max_k=args.max_k)
        s, b = r["strategy_metrics"], r["benchmark_metrics"]
        print(f"\n### {label} — {len(panel)} symbols, {r['n_months']} months ###")
        print(f"  {'':<14}{'CAGR':>9}{'Sharpe':>9}{'MaxDD':>8}")
        print(f"  {'momentum':<14}{s['cagr']*100:>+8.1f}%{s['sharpe']:>9.2f}{s['max_dd']*100:>7.1f}%")
        print(f"  {'EW basket':<14}{b['cagr']*100:>+8.1f}%{b['sharpe']:>9.2f}{b['max_dd']*100:>7.1f}%")
        print(f"  excess: {(s['cagr']-b['cagr'])*100:+.1f}%p CAGR, "
              f"{s['sharpe']-b['sharpe']:+.2f} Sharpe  "
              f"(in-sample + survivorship → treat as MIRAGE)")


if __name__ == "__main__":
    main()
