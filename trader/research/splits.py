# trader/research/splits.py
"""Pre-registered chronological train / validation / holdout splits (P1 foundation).

WHY THIS EXISTS
---------------
In time-series research the holdout (out-of-sample) period must be:
  1. Determined BEFORE any model development or parameter search.
  2. Touched EXACTLY ONCE — at the very end, after all development is done.
  3. The MOST RECENT slice of the available history (future data leaks backward
     through even "innocent" choices like choosing a lookback length).

Violating any of these rules turns the holdout into another validation set and
re-introduces the multiple-testing problem.

SPLITS ARE TIME-ORDERED — NEVER RANDOM
---------------------------------------
Random splits are catastrophically wrong for financial time-series because:
  - They leak future information into training (look-ahead bias).
  - They destroy the temporal autocorrelation structure that strategies exploit.
  - They produce overly optimistic out-of-sample estimates.

Always use chronological_split() from this module, not sklearn train_test_split().

RESEARCH PROTOCOL (short version — full protocol in docs/research-protocol.md)
-------------------------------------------------------------------------------
  1. Pre-register: write down your hypothesis and primary metric BEFORE touching data.
  2. Call chronological_split() ONCE to create splits; store the PeriodSplit.
  3. Develop on TRAIN only.
  4. Tune / select on VALIDATION only (this is where multiple-testing happens).
  5. Touch HOLDOUT exactly ONCE for the final report.
  6. Report trial_count alongside the result.

Public API
----------
    PeriodSplit              — frozen dataclass: (train, validation, holdout) windows.
    chronological_split()    — derive PeriodSplit from a date range.
    filter_bars_to_window()  — filter a list[BarEvent] to [start, end).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from trader.core.events import BarEvent


# ---------------------------------------------------------------------------
# DateWindow type alias
# ---------------------------------------------------------------------------

# A window is (start_date_str, end_date_str) both YYYY-MM-DD, inclusive on
# start, EXCLUSIVE on end (half-open interval [start, end)).
# Exception: for the holdout the end is the last available date (inclusive).
# See filter_bars_to_window for the exact boundary semantics.
DateWindow = tuple[str, str]


# ---------------------------------------------------------------------------
# PeriodSplit
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PeriodSplit:
    """Immutable record of the three chronological research windows.

    Each window is a (start, end) pair of ISO date strings (YYYY-MM-DD).

    Boundary convention (applied by filter_bars_to_window):
      - start is INCLUSIVE  (bars with ts.date() >= start are included)
      - end   is EXCLUSIVE  (bars with ts.date() <  end   are included)
      - For the holdout end, which equals the overall end_date, use
        end_date + 1 day as the exclusive bound (so the last day is included).

    Ordering guarantee:
      train.end   == validation.start
      validation.end == holdout.start
      holdout is the MOST RECENT slice (closest to "now").

    !! THE HOLDOUT MUST BE TOUCHED EXACTLY ONCE — AT THE VERY END !!
    See docs/research-protocol.md for the full protocol.
    """

    train: DateWindow       # (start, end) — earliest slice; develop here
    validation: DateWindow  # (start, end) — middle slice; tune/select here
    holdout: DateWindow     # (start, end) — most recent; ONE final check only

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def train_start(self) -> str:
        return self.train[0]

    @property
    def train_end(self) -> str:
        return self.train[1]

    @property
    def validation_start(self) -> str:
        return self.validation[0]

    @property
    def validation_end(self) -> str:
        return self.validation[1]

    @property
    def holdout_start(self) -> str:
        return self.holdout[0]

    @property
    def holdout_end(self) -> str:
        return self.holdout[1]

    def summary(self) -> str:
        """One-line human-readable summary of the three windows."""
        return (
            f"train=[{self.train_start}, {self.train_end}) | "
            f"validation=[{self.validation_start}, {self.validation_end}) | "
            f"holdout=[{self.holdout_start}, {self.holdout_end}]  "
            f"⚠️  DO NOT touch holdout until final report"
        )


# ---------------------------------------------------------------------------
# chronological_split
# ---------------------------------------------------------------------------

def chronological_split(
    start_date: str,
    end_date: str,
    *,
    train: float = 0.5,
    validation: float = 0.25,
    holdout: float = 0.25,
) -> PeriodSplit:
    """Split a date range chronologically into train / validation / holdout.

    The split is STRICTLY CHRONOLOGICAL:
      [start_date, ..., T1)  → train       (earliest, most data for development)
      [T1,         ..., T2)  → validation  (middle; tune and select here)
      [T2,         ..., end_date]  → holdout   (most recent; locked until final report)

    Args:
        start_date: ISO date string YYYY-MM-DD (inclusive).
        end_date:   ISO date string YYYY-MM-DD (inclusive for holdout end).
        train:      Fraction of total calendar days for train split (default 0.5).
        validation: Fraction for validation split (default 0.25).
        holdout:    Fraction for holdout split (default 0.25).
                    train + validation + holdout must sum to approximately 1.0.

    Returns:
        PeriodSplit with non-overlapping, contiguous windows.

    Raises:
        ValueError: If fractions don't sum to ~1, or if dates are invalid/reversed.

    Notes:
        - Fractions are applied to calendar days (not trading days) for simplicity
          and determinism regardless of the bar calendar.
        - The splits are half-open [start, end) everywhere EXCEPT the holdout end
          which is the overall end_date (inclusive).  filter_bars_to_window handles
          this correctly.
        - !! NEVER use random splits for financial time-series !!
    """
    if abs(train + validation + holdout - 1.0) > 1e-9:
        raise ValueError(
            f"train + validation + holdout must sum to 1.0, "
            f"got {train} + {validation} + {holdout} = {train + validation + holdout}"
        )
    if train <= 0 or validation <= 0 or holdout <= 0:
        raise ValueError("All split fractions must be > 0")

    d_start = _parse_date(start_date)
    d_end   = _parse_date(end_date)

    if d_end <= d_start:
        raise ValueError(
            f"end_date ({end_date}) must be strictly after start_date ({start_date})"
        )

    total_days = (d_end - d_start).days  # exclusive-end count

    # Compute boundary days (integer)
    train_days = max(1, round(total_days * train))
    val_days   = max(1, round(total_days * validation))
    # holdout gets the remainder to avoid rounding gaps
    hold_days  = total_days - train_days - val_days
    if hold_days < 1:
        raise ValueError(
            f"Date range too short ({total_days} days) for three non-trivial splits "
            f"with fractions train={train}, validation={validation}, holdout={holdout}"
        )

    t1 = d_start + timedelta(days=train_days)
    t2 = t1      + timedelta(days=val_days)

    return PeriodSplit(
        train=(start_date, t1.isoformat()),
        validation=(t1.isoformat(), t2.isoformat()),
        # holdout end = overall end_date (inclusive); callers use filter_bars_to_window
        holdout=(t2.isoformat(), end_date),
    )


# ---------------------------------------------------------------------------
# filter_bars_to_window
# ---------------------------------------------------------------------------

def filter_bars_to_window(
    bars: list[BarEvent],
    start: str,
    end: str,
) -> list[BarEvent]:
    """Return bars whose date falls within [start, end).

    Boundary semantics:
      - start is INCLUSIVE: bars with ts.date() >= start_date are included.
      - end   is EXCLUSIVE: bars with ts.date() <  end_date   are included.

    For the HOLDOUT window (where end == overall end_date and is meant to be
    inclusive), pass end as the day AFTER end_date, OR rely on the fact that
    the holdout end stored in PeriodSplit is the last available date — in
    practice, no bars will exist beyond that date, so the exclusive-end
    convention is safe.

    If you want fully-inclusive behaviour on both ends, pass end as the day
    after your intended last date.  The half-open convention is documented
    here and in PeriodSplit so callers can reason about it unambiguously.

    Args:
        bars:  List of BarEvent objects (any order; original order preserved in output).
        start: ISO date string YYYY-MM-DD (inclusive bound).
        end:   ISO date string YYYY-MM-DD (exclusive bound).

    Returns:
        Filtered list of BarEvent objects in their original relative order.
    """
    d_start = _parse_date(start)
    d_end   = _parse_date(end)
    return [b for b in bars if d_start <= b.ts.date() < d_end]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    """Parse an ISO date string YYYY-MM-DD to a date object."""
    try:
        return date.fromisoformat(s)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Expected ISO date string YYYY-MM-DD, got: {s!r}") from exc
