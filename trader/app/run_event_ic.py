# trader/app/run_event_ic.py
"""RESEARCH ONLY — R6: disclosure-event signals through the IC harness.

PRE-REGISTERED experiment (design frozen before any result was computed;
a "preregistration" record is appended to experiments/log.jsonl before the
first evaluation runs).

Hypothesis: post-disclosure drift — the trailing count of specific disclosure
events predicts 21-day forward returns cross-sectionally.

Pre-registered trials (N=6, fixed):
  US (NASDAQ-100 ∩ research_data NASDAQ bars):
    1. us_earnings_8k202_30d   — 8-K:2.02 (results of operations) count, 30d
    2. us_agreements_8k101_30d — 8-K:1.01 (material agreement) count, 30d
    3. us_all_events_30d       — any 8-K/6-K count, 30d
  KR (KOSPI top-200):
    4. kr_supply_contract_30d  — 단일판매ㆍ공급계약체결 count, 30d
    5. kr_insider_ownership_30d— 임원ㆍ주요주주특정증권등소유상황보고서 count, 30d
    6. kr_major_holder_30d     — 주식등의대량보유상황보고서 count, 30d

Protocol: horizon=21 (non-overlapping), min_xs US=30/KR=20, winsorize 1%.
Split: chronological 2021-09-01 → 2026-08-10, 50/25/25. Train reported for
all trials; validation run ONLY for trials with train |t| >= 2.0; HOLDOUT
STAYS LOCKED (holdout_gate discipline). Multiple testing: expected best
|t| under pure noise across N=6 ≈ sqrt(2 ln 6) ≈ 1.89.

NEVER import from live/paper trading or the backtest/live parity path.

Usage:  python -m trader.app.run_event_ic
"""
from __future__ import annotations

import glob
import math
import os
import uuid
from datetime import datetime, timezone

import pandas as pd

from trader.data.manifest import current_git_commit
from trader.data.storage import load_bars
from trader.research.event_signals import make_event_count_signal
from trader.research.experiment_log import ExperimentLog, ExperimentRecord
from trader.research.signal_eval import evaluate_ic
from trader.research.splits import chronological_split, filter_bars_to_window

SPLIT_START, SPLIT_END = "2021-09-01", "2026-08-10"
HORIZON = 21
WINDOW_DAYS = 30
TRAIN_T_GATE = 2.0
N_TRIALS = 6


def _load_panel(market: str) -> dict[str, list]:
    out: dict[str, list] = {}
    for path in sorted(glob.glob(os.path.join("research_data", f"{market}_*.parquet"))):
        bars = load_bars(path)
        if bars:
            out[os.path.basename(path)] = bars
    return out


def _events(path: str) -> list[dict]:
    return pd.read_parquet(path).to_dict("records")


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    commit = current_git_commit()
    split = chronological_split(SPLIT_START, SPLIT_END, train=0.5, validation=0.25, holdout=0.25)
    log = ExperimentLog()

    us_events = _events("event_data/NASDAQ_events.parquet")
    kr_events = _events("event_data/KOSPI_events.parquet")
    us_all_types = sorted({e["event_type"] for e in us_events})

    trials = [
        ("us_earnings_8k202_30d", "US", {"8-K:2.02"}),
        ("us_agreements_8k101_30d", "US", {"8-K:1.01"}),
        ("us_all_events_30d", "US", set(us_all_types)),
        ("kr_supply_contract_30d", "KR", {"단일판매ㆍ공급계약체결"}),
        ("kr_insider_ownership_30d", "KR", {"임원ㆍ주요주주특정증권등소유상황보고서"}),
        ("kr_major_holder_30d", "KR", {"주식등의대량보유상황보고서"}),
    ]

    # ---- pre-registration record (appended BEFORE any evaluation) ----
    log.append(ExperimentRecord(
        experiment_id=str(uuid.uuid4()), created_ts=now, kind="preregistration",
        strategy="R6_event_signals", params={
            "trials": [t[0] for t in trials], "horizon": HORIZON,
            "window_days": WINDOW_DAYS, "train_t_gate": TRAIN_T_GATE,
            "split": split.summary(), "n_trials": N_TRIALS,
            "expected_best_t_noise": round(math.sqrt(2 * math.log(N_TRIALS)), 2),
        },
        universe=["NASDAQ100", "KOSPI_TOP200"], date_start=SPLIT_START,
        date_end=SPLIT_END, dataset_manifest_id=None, code_commit=commit,
        metrics={}, notes="Design frozen before first evaluation. Holdout LOCKED.",
    ))

    panels = {"US": _load_panel("NASDAQ"), "KR": _load_panel("KOSPI")}
    events = {"US": us_events, "KR": kr_events}
    min_xs = {"US": 30, "KR": 20}

    print("=" * 68)
    print("[RESEARCH ONLY] R6 — event-signal IC (pre-registered, N=6 trials)")
    print(f"  split: {split.summary()}")
    print(f"  expected best |t| under noise across {N_TRIALS} trials ≈ "
          f"{math.sqrt(2 * math.log(N_TRIALS)):.2f}")
    print("=" * 68)

    survivors: list[str] = []
    for name, mkt, types in trials:
        fn = make_event_count_signal(events[mkt], event_types=types, window_days=WINDOW_DAYS)
        results = {}
        for phase, (ws, we) in {
            "train": (split.train_start, split.train_end),
            "validation": (split.validation_start, split.validation_end),
        }.items():
            panel = {
                k: filter_bars_to_window(b, ws, we) for k, b in panels[mkt].items()
            }
            panel = {k: b for k, b in panel.items() if b}
            r = evaluate_ic(panel, fn, horizon=HORIZON,
                            min_cross_section=min_xs[mkt], winsorize_pct=0.01)
            results[phase] = r
            if phase == "train" and abs(r.ic_t_stat) < TRAIN_T_GATE:
                break  # gate: don't spend validation on a dead trial

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
            experiment_id=str(uuid.uuid4()), created_ts=now, kind="event_ic",
            strategy=name, params={
                "market": mkt, "horizon": HORIZON, "window_days": WINDOW_DAYS,
                "event_types": sorted(types)[:10], "split": "train(+validation if gated in)",
            },
            universe=sorted(panels[mkt].keys())[:5] + ["..."],
            date_start=SPLIT_START, date_end=SPLIT_END,
            dataset_manifest_id=None, code_commit=commit,
            metrics={
                "train_mean_ic": tr.mean_ic, "train_t": tr.ic_t_stat,
                "train_n": tr.n_periods,
                **({"val_mean_ic": va.mean_ic, "val_t": va.ic_t_stat,
                    "val_n": va.n_periods} if va is not None else {}),
            },
            notes="R6 pre-registered trial. Holdout locked.",
        ))

    print("\n" + "=" * 68)
    print(f"survivors past train gate (|t|>={TRAIN_T_GATE}): {survivors or 'NONE'}")
    print(f"multiple-testing context: N={N_TRIALS} pre-registered trials; "
          f"noise-best ≈ {math.sqrt(2 * math.log(N_TRIALS)):.2f}")
    print("HOLDOUT remains locked; opening it requires holdout_gate discipline.")


if __name__ == "__main__":
    main()
