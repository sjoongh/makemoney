# trader/data/integrity.py
"""RESEARCH/LIVE-SAFE — lightweight data-integrity guards.

Complements trader/data/quality.py (OHLC consistency, non-positive prices,
calendar gaps) with the time/FX/tick guards a real-money run needs:

  - stale data        — last bar older than N days (feed died / clock drift)
  - duplicate dates    — the same trading day appears twice (retry/merge bug)
  - bad FX rate        — non-positive or wildly out-of-band (would mis-size orders)
  - implausible jumps  — day-over-day close move beyond a threshold (bad tick /
                         unhandled split artifact)

Pure functions, no I/O. Callers decide whether a flag is fatal (block trading)
or a warning.

NEVER let a silently-bad rate or stale bar drive a live order.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date

from trader.core.events import BarEvent


@dataclass(frozen=True)
class IntegrityIssue:
    code: str
    detail: str
    severity: str  # WARN | FAIL


def check_stale(bars: list[BarEvent], as_of: _date, *, max_age_days: int = 5) -> IntegrityIssue | None:
    """FAIL if the most recent bar is older than max_age_days before as_of."""
    if not bars:
        return IntegrityIssue("NO_BARS", "empty series", "FAIL")
    last = max(b.ts.date() for b in bars)
    age = (as_of - last).days
    if age > max_age_days:
        return IntegrityIssue("STALE", f"last bar {last} is {age}d old (> {max_age_days})", "FAIL")
    return None


def check_duplicate_dates(bars: list[BarEvent]) -> list[_date]:
    """Return any dates that appear more than once (sorted, unique)."""
    seen: set[_date] = set()
    dups: set[_date] = set()
    for b in bars:
        d = b.ts.date()
        if d in seen:
            dups.add(d)
        seen.add(d)
    return sorted(dups)


def validate_fx_rate(rate: float, *, lo: float = 1e-6, hi: float = 1e7) -> IntegrityIssue | None:
    """FAIL on a non-positive, NaN, or out-of-band FX rate.

    A bad FX rate silently mis-sizes every KRW-settled order — this must hard
    block, never warn-and-continue.
    """
    try:
        r = float(rate)
    except (TypeError, ValueError):
        return IntegrityIssue("FX_BAD", f"non-numeric FX rate {rate!r}", "FAIL")
    if r != r:  # NaN
        return IntegrityIssue("FX_NAN", "FX rate is NaN", "FAIL")
    if r <= 0:
        return IntegrityIssue("FX_NONPOSITIVE", f"FX rate {r} <= 0", "FAIL")
    if not (lo <= r <= hi):
        return IntegrityIssue("FX_OUT_OF_BAND", f"FX rate {r} outside [{lo}, {hi}]", "FAIL")
    return None


def flag_price_jumps(bars: list[BarEvent], *, threshold: float = 0.5) -> list[tuple[_date, float]]:
    """Return (date, pct_move) for day-over-day close moves exceeding threshold.

    A >50% single-day move on a large-cap is almost always a bad tick or an
    unhandled corporate action — worth flagging (WARN) before trusting it.
    """
    out: list[tuple[_date, float]] = []
    sb = sorted(bars, key=lambda b: b.ts)
    for prev, cur in zip(sb, sb[1:]):
        if prev.close > 0:
            move = cur.close / prev.close - 1.0
            if abs(move) > threshold:
                out.append((cur.ts.date(), move))
    return out
