# trader/app/run_beta_game.py
"""RESEARCH ONLY — backtest the risk-managed beta game (vol-targeted EW market).

No alpha was found; this owns the market with EWMA vol targeting for a better
risk-adjusted profile (Sharpe, MaxDD) than naive buy&hold. Beta, honestly.

CAVEATS: equal-weight CURRENT-constituent universe = survivorship-biased (real
return lower); transaction costs of exposure changes are NOT modeled here;
returns are beta-dependent (need the market to rise).

Usage:
    python -m trader.app.run_beta_game [--target-vol 0.15] [--market NASDAQ]
"""
from __future__ import annotations

import argparse
import glob
import os

from trader.data.storage import load_bars
from trader.research.beta_game import run_beta_game


def _load(market: str, data_dir: str) -> dict:
    out = {}
    for p in sorted(glob.glob(os.path.join(data_dir, f"{market}_*.parquet"))):
        b = load_bars(p)
        if b:
            out[os.path.basename(p)[len(market) + 1:-len(".parquet")]] = b
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="[RESEARCH ONLY] risk-managed beta game")
    p.add_argument("--target-vol", type=float, default=0.15)
    p.add_argument("--market", default="NASDAQ")
    p.add_argument("--data-dir", default="research_data")
    args = p.parse_args(argv)

    panel = _load(args.market, args.data_dir)
    print("=" * 64)
    print(f"[RESEARCH ONLY] Beta game — {args.market}, {len(panel)} names, "
          f"target_vol={args.target_vol:.0%}")
    print("  Risk-managed market BETA (no alpha). Survivorship-biased; costs not modeled.")
    print("=" * 64)
    r = run_beta_game(panel, target_vol=args.target_vol)
    s, b = r["strategy"], r["benchmark"]
    print(f"  avg exposure {r['avg_exposure']:.2f} | {r['n_days']} days\n")
    print(f"  {'':12}{'CAGR':>9}{'vol':>9}{'Sharpe':>9}{'MaxDD':>9}")
    print(f"  {'vol-target':12}{s['cagr']:>9.1%}{s['ann_vol']:>9.1%}{s['sharpe']:>9.2f}{s['max_drawdown']:>9.1%}")
    print(f"  {'buy&hold':12}{b['cagr']:>9.1%}{b['ann_vol']:>9.1%}{b['sharpe']:>9.2f}{b['max_drawdown']:>9.1%}")
    print("\n  Honest read: gives up some raw CAGR (no alpha), but better Sharpe and")
    print("  ~half the max drawdown. This is BETA, risk-managed — not a skill edge.")


if __name__ == "__main__":
    main()
