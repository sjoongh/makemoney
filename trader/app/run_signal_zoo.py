# trader/app/run_signal_zoo.py
"""RESEARCH ONLY — split-disciplined signal zoo with multiple-testing honesty.

Evaluates a battery of candidate signals' cross-sectional IC on the TRAIN and
VALIDATION splits only (chronological; trader/research/splits.py).  The HOLDOUT
is never touched here — it is opened exactly once, for a single pre-registered
survivor, via --holdout (gated by trader/research/holdout_gate.py).

Every (signal, market) evaluation is appended to the experiment log, and a
multiple-testing haircut is printed for the number of trials.

NEVER import from live/paper trading or the backtest/live parity path.

Usage:
    python -m trader.app.run_signal_zoo                  # train+val scan
    python -m trader.app.run_signal_zoo --holdout momentum_12_1@US
"""
from __future__ import annotations

import argparse
import glob
import os
import uuid
from datetime import datetime, timezone

from trader.data.manifest import current_git_commit
from trader.data.storage import load_bars
from trader.research.experiment_log import (
    ExperimentLog,
    ExperimentRecord,
    multiple_testing_warning,
)
from trader.research.holdout_gate import assert_holdout_allowed, preregister
from trader.research.signal_eval import (
    amihud_illiquidity,
    evaluate_ic,
    long_term_reversal,
    low_volatility,
    max_daily_return,
    momentum_3_1,
    momentum_6_1,
    momentum_12_1,
    momentum_12_2,
    pct_of_52w_high,
    return_skewness,
    short_term_reversal,
    volume_trend,
)
from trader.research.splits import chronological_split

SIGNALS = {
    "momentum_12_1": momentum_12_1,
    "momentum_12_2": momentum_12_2,
    "momentum_6_1": momentum_6_1,
    "momentum_3_1": momentum_3_1,
    "reversal_5": lambda h: short_term_reversal(h, 5),
    "reversal_21": lambda h: short_term_reversal(h, 21),
    "long_term_reversal": long_term_reversal,
    "low_volatility_60": lambda h: low_volatility(h, 60),
    "max_lottery_21": lambda h: max_daily_return(h, 21),
    "pct_52w_high": pct_of_52w_high,
    "amihud_illiquidity": lambda h: amihud_illiquidity(h, 21),
    "volume_trend": lambda h: volume_trend(h, 21, 63),
    "return_skewness_60": lambda h: return_skewness(h, 60),
}
MARKETS = {"US": ("NASDAQ", 30), "KR": ("KOSPI", 20)}


def _load(market: str, data_dir: str) -> dict[str, list]:
    out: dict[str, list] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, f"{market}_*.parquet"))):
        bars = load_bars(path)
        if bars:
            out[os.path.basename(path)] = bars
    return out


def _date_range(panel: dict[str, list]) -> tuple[str, str]:
    dates = [b.ts.date() for bars in panel.values() for b in bars]
    return min(dates).isoformat(), max(dates).isoformat()


def _eval_window(panel, fn, horizon, min_xs, win) -> dict:
    r = evaluate_ic(panel, fn, horizon=horizon, min_cross_section=min_xs,
                    winsorize_pct=0.01, date_start=win[0], date_end=win[1],
                    strict_split=True)
    return {"mean_ic": r.mean_ic, "ic_t_stat": r.ic_t_stat,
            "mean_rank_ic": r.mean_rank_ic, "n_periods": r.n_periods}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="[RESEARCH ONLY] split-disciplined signal zoo")
    p.add_argument("--horizon", type=int, default=21)
    p.add_argument("--data-dir", default="research_data")
    p.add_argument("--holdout", default=None,
                   help="open the holdout ONCE for one survivor: signal@market (e.g. momentum_12_1@US)")
    args = p.parse_args(argv)

    now = datetime.now(tz=timezone.utc).isoformat()
    commit = current_git_commit()
    log = ExperimentLog()

    panels = {m: _load(spec[0], args.data_dir) for m, spec in MARKETS.items()}
    splits = {m: chronological_split(*_date_range(panels[m])) for m in MARKETS if panels[m]}

    if args.holdout:
        _run_holdout(args, panels, splits, now, commit, log)
        return

    print("=" * 78)
    print("[RESEARCH ONLY] Signal zoo — TRAIN + VALIDATION only (holdout reserved)")
    print("  Split-disciplined IC; forward windows never cross a split boundary.")
    print("=" * 78)

    n_trials = 0
    for mkt, (market, min_xs) in MARKETS.items():
        panel = panels[mkt]
        if not panel:
            continue
        sp = splits[mkt]
        print(f"\n### {mkt} ({market}) — {len(panel)} symbols ###")
        print(f"  train {sp.train}  | val {sp.validation}  | holdout {sp.holdout} (locked)")
        print(f"  {'signal':<20} {'train IC':>9} {'train t':>8} {'val IC':>9} {'val t':>8}")
        for name, fn in SIGNALS.items():
            tr = _eval_window(panel, fn, args.horizon, min_xs, sp.train)
            va = _eval_window(panel, fn, args.horizon, min_xs, sp.validation)
            n_trials += 1
            print(f"  {name:<20} {tr['mean_ic']:>+9.4f} {tr['ic_t_stat']:>+8.2f} "
                  f"{va['mean_ic']:>+9.4f} {va['ic_t_stat']:>+8.2f}")
            log.append(ExperimentRecord(
                experiment_id=str(uuid.uuid4()), created_ts=now, kind="ic_zoo",
                strategy=name, params={"market": mkt, "horizon": args.horizon,
                                       "split": "train+validation"},
                universe=sorted(panel.keys()),
                date_start=sp.train[0], date_end=sp.validation[1],
                dataset_manifest_id=None, code_commit=commit,
                metrics={"train": tr, "validation": va},
                notes="signal-zoo IC scan (exploratory; holdout reserved)"))

    print("\n" + "-" * 78)
    print(multiple_testing_warning(n_trials))
    print(f"\nLogged {n_trials} trials to the experiment log. To open the holdout for a\n"
          "single survivor (once): --holdout <signal>@<market>")


def _run_holdout(args, panels, splits, now, commit, log) -> None:
    try:
        sig_name, mkt = args.holdout.split("@")
    except ValueError:
        raise SystemExit("--holdout must be signal@market, e.g. momentum_12_1@US")
    if sig_name not in SIGNALS or mkt not in MARKETS:
        raise SystemExit(f"unknown signal/market: {args.holdout}")

    market, min_xs = MARKETS[mkt]
    panel = panels[mkt]
    sp = splits[mkt]
    spec = {"signal": sig_name, "market": mkt, "horizon": args.horizon,
            "min_cross_section": min_xs, "n_symbols": len(panel),
            "holdout": list(sp.holdout)}

    # one-time pre-registration + gate (refuses any second/different spec)
    preregister(spec, created_ts=now)
    assert_holdout_allowed(spec, created_ts=now)

    print("=" * 78)
    print(f"[RESEARCH ONLY] HOLDOUT — opened once for {sig_name} @ {mkt}")
    print(f"  holdout window: {sp.holdout}")
    print("=" * 78)
    res = _eval_window(panel, SIGNALS[sig_name], args.horizon, min_xs, sp.holdout)
    print(f"  mean IC   = {res['mean_ic']:+.4f}")
    print(f"  IC t-stat = {res['ic_t_stat']:+.2f}  "
          f"({'significant' if abs(res['ic_t_stat']) >= 2 else 'NOT significant'} at |t|>=2)")
    print(f"  rank IC   = {res['mean_rank_ic']:+.4f}   over {res['n_periods']} periods")
    log.append(ExperimentRecord(
        experiment_id=str(uuid.uuid4()), created_ts=now, kind="ic_holdout",
        strategy=sig_name, params={"market": mkt, "horizon": args.horizon, "split": "holdout"},
        universe=sorted(panel.keys()), date_start=sp.holdout[0], date_end=sp.holdout[1],
        dataset_manifest_id=None, code_commit=commit, metrics=res,
        notes="HOLDOUT opened once (pre-registered)"))


if __name__ == "__main__":
    main()
