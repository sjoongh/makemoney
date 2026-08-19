# trader/app/run_flow_ic.py
"""RESEARCH ONLY — R7: KR investor-flow signals through the IC harness.

PRE-REGISTERED experiment (design frozen before any result; preregistration
record appended to experiments/log.jsonl before the first evaluation).

Hypothesis: smart-money flow persistence/pressure — the 7-day turnover-
normalized net buying of 기관/외국인 predicts 21-day forward returns
cross-sectionally on KOSPI-200. (Two-sided: contrarian sign is admissible.)

Pre-registered trials (N=3, fixed):
  1. kr_frgn_imbalance_7d  — 외국인 7d Σnet/Σvolume
  2. kr_inst_imbalance_7d  — 기관 7d Σnet/Σvolume
  3. kr_smart_imbalance_7d — 기관+외국인 combined

Protocol: horizon=21 non-overlapping, min_xs=20, winsorize 1%,
split chronological 2021-09-01 → 2026-08-14 (50/25/25), train gate |t|>=2.0
before validation, HOLDOUT LOCKED. Expected best |t| under noise across
N=3 ≈ sqrt(2 ln 3) ≈ 1.48.

NEVER import from live/paper trading or the backtest/live parity path.

Usage:  python -m trader.app.run_flow_ic
"""
from __future__ import annotations

import glob
import math
import os
import uuid
from datetime import datetime, timezone

from trader.data.manifest import current_git_commit
from trader.data.naver_flows import load_flows
from trader.data.storage import load_bars
from trader.research.experiment_log import ExperimentLog, ExperimentRecord
from trader.research.flow_signals import make_flow_imbalance_signal
from trader.research.signal_eval import evaluate_ic
from trader.research.splits import chronological_split, filter_bars_to_window

SPLIT_START, SPLIT_END = "2021-09-01", "2026-08-14"
HORIZON = 21
WINDOW_DAYS = 7
TRAIN_T_GATE = 2.0
N_TRIALS = 3


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    commit = current_git_commit()
    split = chronological_split(SPLIT_START, SPLIT_END, train=0.5, validation=0.25, holdout=0.25)
    log = ExperimentLog()
    flows = load_flows("flow_data/KOSPI_flows.parquet")

    trials = [
        ("kr_frgn_imbalance_7d", "frgn_net"),
        ("kr_inst_imbalance_7d", "inst_net"),
        ("kr_smart_imbalance_7d", "smart"),
    ]

    log.append(ExperimentRecord(
        experiment_id=str(uuid.uuid4()), created_ts=now, kind="preregistration",
        strategy="R7_flow_signals", params={
            "trials": [t[0] for t in trials], "horizon": HORIZON,
            "window_days": WINDOW_DAYS, "train_t_gate": TRAIN_T_GATE,
            "split": split.summary(), "n_trials": N_TRIALS,
            "expected_best_t_noise": round(math.sqrt(2 * math.log(N_TRIALS)), 2),
            "flow_rows": len(flows),
        },
        universe=["KOSPI_TOP200"], date_start=SPLIT_START, date_end=SPLIT_END,
        dataset_manifest_id=None, code_commit=commit, metrics={},
        notes="R7 design frozen before first evaluation. Holdout LOCKED.",
    ))

    panel_full = {}
    for path in sorted(glob.glob(os.path.join("research_data", "KOSPI_*.parquet"))):
        bars = load_bars(path)
        if bars:
            panel_full[os.path.basename(path)] = bars

    print("=" * 68)
    print("[RESEARCH ONLY] R7 — KR flow-signal IC (pre-registered, N=3 trials)")
    print(f"  flow rows: {len(flows)} | split: {split.summary()}")
    print(f"  expected best |t| under noise across {N_TRIALS} ≈ "
          f"{math.sqrt(2 * math.log(N_TRIALS)):.2f}")
    print("=" * 68)

    survivors: list[str] = []
    for name, field in trials:
        fn = make_flow_imbalance_signal(flows, field=field, window_days=WINDOW_DAYS)
        results = {}
        for phase, (ws, we) in {
            "train": (split.train_start, split.train_end),
            "validation": (split.validation_start, split.validation_end),
        }.items():
            panel = {k: filter_bars_to_window(b, ws, we) for k, b in panel_full.items()}
            panel = {k: b for k, b in panel.items() if b}
            r = evaluate_ic(panel, fn, horizon=HORIZON,
                            min_cross_section=20, winsorize_pct=0.01)
            results[phase] = r
            if phase == "train" and abs(r.ic_t_stat) < TRAIN_T_GATE:
                break

        tr = results["train"]
        line = (f"\n-- {name} --\n  train: mean_ic={tr.mean_ic:+.4f} "
                f"t={tr.ic_t_stat:+.2f} n={tr.n_periods}")
        va = results.get("validation")
        if va is not None:
            survivors.append(name)
            line += (f"\n  VALIDATION: mean_ic={va.mean_ic:+.4f} "
                     f"t={va.ic_t_stat:+.2f} n={va.n_periods}")
        else:
            line += f"\n  validation: SKIPPED (train |t| < {TRAIN_T_GATE})"
        print(line)

        log.append(ExperimentRecord(
            experiment_id=str(uuid.uuid4()), created_ts=now, kind="flow_ic",
            strategy=name, params={
                "market": "KR", "horizon": HORIZON, "window_days": WINDOW_DAYS,
                "field": field,
            },
            universe=["KOSPI_TOP200"], date_start=SPLIT_START, date_end=SPLIT_END,
            dataset_manifest_id=None, code_commit=commit,
            metrics={
                "train_mean_ic": tr.mean_ic, "train_t": tr.ic_t_stat,
                "train_n": tr.n_periods,
                **({"val_mean_ic": va.mean_ic, "val_t": va.ic_t_stat,
                    "val_n": va.n_periods} if va is not None else {}),
            },
            notes="R7 pre-registered trial. Holdout locked.",
        ))

    print("\n" + "=" * 68)
    print(f"survivors past train gate (|t|>={TRAIN_T_GATE}): {survivors or 'NONE'}")
    print("HOLDOUT remains locked; opening it requires holdout_gate discipline.")


if __name__ == "__main__":
    main()
