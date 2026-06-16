# trader/research/experiment_log.py
"""Multiple-testing discipline — experiment log and trial-count warnings (P1 foundation).

The core problem: once you try many strategies / parameter sets / universes /
lookback windows, false positives are inevitable.  A "good" backtest result
that is the best of N attempts is almost certainly noise, not edge.

This module provides:
  - ExperimentRecord  — frozen dataclass capturing one experiment's full context.
  - ExperimentLog     — append-only JSONL log; survives process restarts.
  - multiple_testing_warning — honest, escalating message about N-trial risk.

Usage in research scripts
-------------------------
    from trader.research.experiment_log import ExperimentLog, ExperimentRecord
    from trader.data.manifest import current_git_commit

    log = ExperimentLog()
    rec = ExperimentRecord(
        experiment_id="mom_v1_run03",
        created_ts="2026-06-17T12:00:00Z",
        kind="momentum",
        strategy="cross_sectional_momentum",
        params={"lookback": 252, "skip": 21, "top_pct": 0.30},
        universe=["AAPL", "MSFT", "AMZN"],
        date_start="2020-01-01",
        date_end="2024-12-31",
        dataset_manifest_id="sha256:abc123",
        code_commit=current_git_commit(),
        metrics={"sharpe": 0.72, "cagr": 0.11},
    )
    log.append(rec)
    n = log.trial_count(kind="momentum")
    print(multiple_testing_warning(n))
"""
from __future__ import annotations

import fcntl
import json
import math
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# Default path relative to project root (experiments/ is gitignored by default)
_DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "experiments" / "log.jsonl"


# ---------------------------------------------------------------------------
# ExperimentRecord
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExperimentRecord:
    """Immutable record for one experiment run.

    Fields
    ------
    experiment_id:        Unique string ID (caller-supplied or auto-generated UUID).
    created_ts:           ISO-8601 timestamp — injected by caller; no wall clock here.
    kind:                 Category, e.g. "evaluate", "momentum", "custom".
    strategy:             Strategy name, e.g. "cross_sectional_momentum".
    params:               Dict of all varied hyperparameters (frozen as tuple internally).
    universe:             Sorted list of ticker strings used in this run.
    date_start:           ISO date of backtest start window (YYYY-MM-DD).
    date_end:             ISO date of backtest end window (YYYY-MM-DD).
    dataset_manifest_id:  content_hash or manifest ID string (None if not tracked).
    code_commit:          Git HEAD SHA at run time (None if not in a git repo).
    metrics:              Dict of computed performance metrics (e.g. sharpe, cagr).
    notes:                Free-form notes string.
    """

    experiment_id: str
    created_ts: str
    kind: str
    strategy: str
    params: dict
    universe: list
    date_start: str
    date_end: str
    dataset_manifest_id: Optional[str]
    code_commit: Optional[str]
    metrics: dict
    notes: str = ""

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ExperimentRecord":
        """Deserialise from a plain dict (as loaded from JSONL)."""
        return cls(**d)


# ---------------------------------------------------------------------------
# ExperimentLog
# ---------------------------------------------------------------------------

class ExperimentLog:
    """Append-only experiment journal backed by a JSONL file.

    Each line in the file is one JSON object representing one ExperimentRecord.
    Writes are atomic (file lock + flush + sync) so concurrent appends from
    different processes do not corrupt the file.

    Args:
        path: Path to the JSONL file.  Defaults to experiments/log.jsonl in
              the project root.  The parent directory is created if missing.
    """

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self._path = Path(path) if path is not None else _DEFAULT_LOG_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(self, record: ExperimentRecord) -> None:
        """Append one ExperimentRecord to the log.

        Writes are atomic: the file is opened in append mode, an exclusive
        advisory lock is held while the line is written and flushed, then
        the lock is released.  On platforms where fcntl is unavailable (e.g.
        Windows) the lock is skipped but the append is still performed.
        """
        line = json.dumps(record.to_dict(), ensure_ascii=False) + "\n"
        with open(self._path, "a", encoding="utf-8") as fh:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX)
            except Exception:
                pass  # non-POSIX platforms: best-effort
            try:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                try:
                    fcntl.flock(fh, fcntl.LOCK_UN)
                except Exception:
                    pass

    def all(self) -> list[dict]:
        """Return all logged records as plain dicts (in append order).

        Returns an empty list if the log file does not yet exist.
        """
        if not self._path.exists():
            return []
        records: list[dict] = []
        with open(self._path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # skip malformed lines
        return records

    def trial_count(
        self,
        *,
        kind: Optional[str] = None,
        strategy: Optional[str] = None,
    ) -> int:
        """Count logged experiments matching the given filters.

        Args:
            kind:     If given, only count records whose ``kind`` matches.
            strategy: If given, only count records whose ``strategy`` matches.
                      Both filters are ANDed together.

        Returns:
            Integer count of matching records.
        """
        total = 0
        for rec in self.all():
            if kind is not None and rec.get("kind") != kind:
                continue
            if strategy is not None and rec.get("strategy") != strategy:
                continue
            total += 1
        return total


# ---------------------------------------------------------------------------
# multiple_testing_warning
# ---------------------------------------------------------------------------

def multiple_testing_warning(n_trials: int) -> str:
    """Return an honest, escalating warning about multiple-testing risk.

    Statistical rationale
    ----------------------
    The maximum of n independent standard-normal draws (best-of-n Sharpe under
    pure noise) grows approximately as sqrt(2 ln n):
      n=1  → 0.00   (no selection)
      n=5  → 1.79   (already looks meaningful)
      n=10 → 2.15
      n=20 → 2.45
      n=50 → 2.80
    A "good" backtest Sharpe of 1.5 after 20 attempts would be expected under
    pure noise roughly half the time.  The more trials, the lower the bar for
    a spurious result to appear excellent.

    Args:
        n_trials: Total number of experiments logged (possibly filtered by
                  kind/strategy before passing here).

    Returns:
        A string warning (may be empty for n=0, mild for n<5, escalating above).
    """
    if n_trials <= 0:
        return ""

    # Expected best-of-n Sharpe under pure noise: ~sqrt(2 ln n)
    expected_best = math.sqrt(2.0 * math.log(n_trials)) if n_trials > 1 else 0.0

    if n_trials == 1:
        return (
            f"[multiple-testing] 1 trial logged. "
            f"No selection bias yet — pre-register before varying parameters."
        )

    if n_trials < 5:
        return (
            f"[multiple-testing] {n_trials} trials logged. "
            f"Expected best-of-{n_trials} Sharpe under pure noise ≈ {expected_best:.2f}. "
            f"Early stage — keep a pre-registered hypothesis and use the locked holdout."
        )

    if n_trials < 10:
        return (
            f"[multiple-testing] ⚠️  {n_trials} trials logged. "
            f"Expected best-of-{n_trials} Sharpe under pure noise ≈ {expected_best:.2f} "
            f"(rule: max of N N(0,1) draws grows ~sqrt(2 ln N)). "
            f"A promising result at this stage needs holdout confirmation."
        )

    # n >= 10: strong warning
    return (
        f"[multiple-testing] ⚠️  {n_trials} trials logged; "
        f"expected best-of-{n_trials} Sharpe under pure noise is materially >0 "
        f"(≈ {expected_best:.2f}, rule: max of N N(0,1) draws grows ~sqrt(2 ln N)). "
        f"A good result here is likely overfit. "
        f"Pre-register your hypothesis and use the locked holdout before drawing conclusions."
    )
