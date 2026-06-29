# trader/app/run_beta_paper.py
"""RESEARCH ONLY — daily forward PAPER tracker for the beta/defensive strategy.

Each run recomputes the risk-managed beta strategy (vol-target [+ trend]) on the
current research_data snapshot and appends one snapshot to beta_paper_track.jsonl
(idempotent per market date). As the accumulator extends research_data daily, the
track advances forward — accumulating a real paper track record of the *sensible*
strategy (vs the no-edge technical one), to compare against the market over time.

This is a simulated/paper track (no broker orders). NEVER places real orders.

Usage (cron, daily after the accumulator):
    python -m trader.app.run_beta_paper [--target-vol 0.15] [--trend-window 200]
"""
from __future__ import annotations

import argparse
import glob
import os
from datetime import datetime, timezone

from trader.data.storage import load_bars
from trader.research.beta_game import append_beta_track, run_beta_game


def _load(market: str, data_dir: str) -> dict:
    out = {}
    for p in sorted(glob.glob(os.path.join(data_dir, f"{market}_*.parquet"))):
        b = load_bars(p)
        if b:
            out[os.path.basename(p)[len(market) + 1:-len(".parquet")]] = b
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="[RESEARCH ONLY] beta/defensive paper tracker")
    p.add_argument("--target-vol", type=float, default=0.15)
    p.add_argument("--trend-window", type=int, default=200,
                   help="trailing-MA cash switch window; 0 disables (vol-target only)")
    p.add_argument("--market", default="NASDAQ")
    p.add_argument("--data-dir", default="research_data")
    args = p.parse_args(argv)

    panel = _load(args.market, args.data_dir)
    trend = args.trend_window or None
    res = run_beta_game(panel, target_vol=args.target_vol, trend_window=trend)

    s, b = res["strategy"], res["benchmark"]
    record = {
        "as_of": datetime.now(tz=timezone.utc).date().isoformat(),
        "last_date": res["last_date"],
        "market": args.market,
        "n_days": res["n_days"],
        "target_vol": args.target_vol,
        "trend_window": trend,
        "latest_exposure": res["latest_exposure"],
        "strat_equity": res["strat_equity"],
        "bench_equity": res["bench_equity"],
        "strat_cagr": s["cagr"], "strat_sharpe": s["sharpe"], "strat_maxdd": s["max_drawdown"],
        "bench_cagr": b["cagr"], "bench_sharpe": b["sharpe"], "bench_maxdd": b["max_drawdown"],
    }
    appended = append_beta_track(record)

    print(f"[beta-paper] {args.market} last_date={res['last_date']} appended={appended}")
    print(f"  exposure={res['latest_exposure']:.2f} | strat eq={res['strat_equity']:.3f} "
          f"bench eq={res['bench_equity']:.3f}")
    print(f"  strat: CAGR {s['cagr']:.1%} Sharpe {s['sharpe']:.2f} MaxDD {s['max_drawdown']:.1%} | "
          f"bench: CAGR {b['cagr']:.1%} Sharpe {b['sharpe']:.2f} MaxDD {b['max_drawdown']:.1%}")


if __name__ == "__main__":
    main()
