# tests/test_event_signals.py
"""Phase 7 (free-data expansion) — event → SignalFn adapter for the IC harness.

The adapter must be point-in-time honest: an event accepted on date d is
usable only from d + embargo_days (date-granular acceptance ⇒ conservative
next-day embargo by default).
"""
from __future__ import annotations

from datetime import datetime, timezone

from trader.core.events import BarEvent
from trader.research.event_signals import make_event_count_signal


def _bar(symbol: str, day: str) -> BarEvent:
    ts = datetime.fromisoformat(day + "T00:00:00+00:00").astimezone(timezone.utc)
    return BarEvent(symbol=symbol, ts=ts, open=1, high=1, low=1, close=1, volume=100)


EVENTS = [
    {"symbol": "AAPL", "event_type": "8-K:2.02", "accepted_ts": "2026-07-20T21:00:00.000Z"},
    {"symbol": "AAPL", "event_type": "8-K:2.02", "accepted_ts": "2026-07-24T21:00:00.000Z"},
    {"symbol": "AAPL", "event_type": "8-K:5.02", "accepted_ts": "2026-07-24T21:00:00.000Z"},
    {"symbol": "NVDA", "event_type": "8-K:2.02", "accepted_ts": "2026-06-01T21:00:00.000Z"},
    # DART rows carry date-only accepted_ts
    {"symbol": "005930", "event_type": "주요사항보고서", "accepted_ts": "2026-07-23"},
]


def test_counts_matching_events_in_window():
    fn = make_event_count_signal(EVENTS, event_types={"8-K:2.02"}, window_days=10)
    bars = [_bar("AAPL", "2026-07-15"), _bar("AAPL", "2026-07-22")]
    assert fn(bars) == 1.0  # 07-20 usable at t=07-22; 07-24 is in the future


def test_embargo_excludes_event_accepted_on_t():
    fn = make_event_count_signal(EVENTS, event_types={"8-K:2.02"}, window_days=10)
    bars = [_bar("AAPL", "2026-07-24")]
    # 07-24 event not yet usable at t=07-24 (embargo 1 day); 07-20 is.
    assert fn(bars) == 1.0


def test_event_usable_from_next_day():
    fn = make_event_count_signal(EVENTS, event_types={"8-K:2.02"}, window_days=10)
    bars = [_bar("AAPL", "2026-07-25")]
    assert fn(bars) == 2.0  # both 07-20 and 07-24 now usable


def test_window_expires_old_events():
    fn = make_event_count_signal(EVENTS, event_types={"8-K:2.02"}, window_days=3)
    bars = [_bar("AAPL", "2026-07-25")]
    assert fn(bars) == 1.0  # 07-20 outside 3-day window


def test_no_events_symbol_scores_zero_not_none():
    fn = make_event_count_signal(EVENTS, event_types={"8-K:2.02"}, window_days=10)
    bars = [_bar("MSFT", "2026-07-25")]
    assert fn(bars) == 0.0  # zero is informative cross-sectionally


def test_empty_bars_returns_none():
    fn = make_event_count_signal(EVENTS, event_types={"8-K:2.02"}, window_days=10)
    assert fn([]) is None


def test_date_only_accepted_ts_supported():
    fn = make_event_count_signal(EVENTS, event_types={"주요사항보고서"}, window_days=5)
    assert fn([_bar("005930", "2026-07-23")]) == 0.0  # same-day: embargoed
    assert fn([_bar("005930", "2026-07-24")]) == 1.0


def test_symbol_dataclass_bars_resolve_to_ticker():
    # Real bars carry Symbol(ticker=..., market=...), not a plain string —
    # the adapter must match events by ticker either way.
    from trader.core.events import Market, Symbol

    fn = make_event_count_signal(EVENTS, event_types={"8-K:2.02"}, window_days=10)
    sym = Symbol(ticker="AAPL", market=Market.NASDAQ, currency="USD")
    bars = [BarEvent(symbol=sym, ts=_bar("AAPL", "2026-07-25").ts,
                     open=1, high=1, low=1, close=1, volume=100)]
    assert fn(bars) == 2.0


def test_multiple_event_types_union():
    fn = make_event_count_signal(
        EVENTS, event_types={"8-K:2.02", "8-K:5.02"}, window_days=10
    )
    assert fn([_bar("AAPL", "2026-07-25")]) == 3.0
