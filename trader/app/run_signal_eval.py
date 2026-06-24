# trader/app/run_signal_eval.py
"""RESEARCH ONLY — run the cross-sectional IC harness on the local dataset.

Answers "does a signal's ranking predict forward returns?" for the standard
candidate signals, per market, with non-overlapping windows and a tradable
(t+1 open -> t+h close) forward return.

NEVER import from live/paper trading or the backtest/live parity path.

Usage:
    python -m trader.app.run_signal_eval [--horizon N] [--us-min M] [--kr-min M]

NOTE on multiple testing: this scans several signals x markets x horizons.
None of these are pre-registered hypotheses — treat results as EXPLORATORY.
A surviving signal must be re-checked under the pre-registered holdout split
(trader/research/splits.py) before any alpha claim.
"""
from __future__ import annotations

import argparse
import glob
import os

from trader.data.storage import load_bars
from trader.research.signal_eval import (
    evaluate_ic,
    momentum_12_1,
    short_term_reversal,
)


def _load(market: str, data_dir: str) -> dict[str, list]:
    out: dict[str, list] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, f"{market}_*.parquet"))):
        bars = load_bars(path)
        if bars:
            out[os.path.basename(path)] = bars
    return out


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="[RESEARCH ONLY] cross-sectional IC harness")
    p.add_argument("--horizon", type=int, default=21, help="forward-return horizon (trading days)")
    p.add_argument("--us-min", type=int, default=30, help="min cross-section for US")
    p.add_argument("--kr-min", type=int, default=20, help="min cross-section for KR")
    p.add_argument("--winsorize", type=float, default=0.01, help="forward-return tail clip")
    p.add_argument("--data-dir", default="research_data")
    args = p.parse_args(argv)

    print("=" * 64)
    print("[RESEARCH ONLY] Cross-sectional IC — EXPLORATORY (not pre-registered)")
    print("  Forward return: t+1 open -> t+horizon close. Non-overlapping windows.")
    print("=" * 64)

    signals = [
        ("12-1 momentum", momentum_12_1),
        ("5d reversal", lambda h: short_term_reversal(h, 5)),
    ]
    markets = [
        ("US (NASDAQ)", "NASDAQ", args.us_min),
        ("KR (KOSPI)", "KOSPI", args.kr_min),
    ]

    for label, market, mxs in markets:
        panel = _load(market, args.data_dir)
        print(f"\n### {label} — {len(panel)} symbols (min_xs={mxs}) ###")
        if not panel:
            print("  (no data)")
            continue
        for sig_name, fn in signals:
            r = evaluate_ic(
                panel, fn,
                horizon=args.horizon,
                min_cross_section=mxs,
                winsorize_pct=args.winsorize,
            )
            print(f"\n-- {sig_name} --")
            print("  " + r.summary().replace("\n", "\n  "))


if __name__ == "__main__":
    main()
