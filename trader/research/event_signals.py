# trader/research/event_signals.py
"""RESEARCH ONLY — adapt disclosure events into SignalFns for the IC harness.

Free-data expansion Phase 7 (see .omc/specs/deep-interview-free-data-expansion.md).
``make_event_count_signal`` closes over an event table (event_store rows) and
returns a SignalFn compatible with trader.research.signal_eval: given the
point-in-time bar history of ONE symbol, it scores the trailing count of
matching events.

Point-in-time rule: an event with acceptance date ``d`` is usable from
``d + embargo_days`` (default 1). Acceptance timestamps may be full ISO
instants (EDGAR) or date-only strings (DART); both truncate to the date —
the conservative reading, since a date-only acceptance could be intraday.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import date, timedelta
from typing import Optional

from trader.core.events import BarEvent
from trader.research.signal_eval import SignalFn


def _accepted_date(accepted_ts: str) -> date:
    return date.fromisoformat(accepted_ts[:10])


def make_event_count_signal(
    events: list[dict],
    *,
    event_types: set[str],
    window_days: int,
    embargo_days: int = 1,
) -> SignalFn:
    """SignalFn: count of matching events in [t - window_days, t - embargo_days].

    Symbols with no events score 0.0 (informative cross-sectionally), an
    empty bar history scores None (no opinion).
    """
    by_symbol: dict[str, list[date]] = {}
    for e in events:
        if e["event_type"] in event_types:
            by_symbol.setdefault(e["symbol"], []).append(_accepted_date(e["accepted_ts"]))
    for dates in by_symbol.values():
        dates.sort()

    def signal(bars: list[BarEvent]) -> Optional[float]:
        if not bars:
            return None
        t = bars[-1].ts.date()
        # Bars carry Symbol dataclasses in real panels, plain strings in
        # fixtures — resolve either to the ticker string used by event rows.
        sym = bars[-1].symbol
        dates = by_symbol.get(getattr(sym, "ticker", None) or str(sym))
        if not dates:
            return 0.0
        lo = t - timedelta(days=window_days)
        hi = t - timedelta(days=embargo_days)
        return float(bisect_right(dates, hi) - bisect_left(dates, lo))

    return signal
