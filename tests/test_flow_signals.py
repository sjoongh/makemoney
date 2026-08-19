# tests/test_flow_signals.py
"""R7 — investor-flow → SignalFn adapter (turnover-normalized imbalance).

Score at t = Σ net(field) / Σ volume over [t-window, t-embargo].
Missing coverage → None (unknown flows ≠ zero flows, unlike event counts).
"""
from __future__ import annotations

from datetime import datetime, timezone

from trader.core.events import BarEvent
from trader.research.flow_signals import make_flow_imbalance_signal


def _bar(symbol: str, day: str) -> BarEvent:
    ts = datetime.fromisoformat(day + "T00:00:00+00:00").astimezone(timezone.utc)
    return BarEvent(symbol=symbol, ts=ts, open=1, high=1, low=1, close=1, volume=100)


FLOWS = [
    {"symbol": "005930", "date": "2026-08-10", "volume": 1000, "inst_net": 100, "frgn_net": -50},
    {"symbol": "005930", "date": "2026-08-11", "volume": 3000, "inst_net": -200, "frgn_net": 150},
    {"symbol": "005930", "date": "2026-08-14", "volume": 2000, "inst_net": 300, "frgn_net": 100},
    {"symbol": "000660", "date": "2026-08-11", "volume": 500, "inst_net": 50, "frgn_net": 50},
]


def test_imbalance_is_net_over_volume_in_window():
    fn = make_flow_imbalance_signal(FLOWS, field="inst_net", window_days=7)
    # t=08-15: window [08-08, 08-14] → rows 08-10, 08-11, 08-14
    assert fn([_bar("005930", "2026-08-15")]) == (100 - 200 + 300) / 6000


def test_embargo_excludes_same_day_flow():
    fn = make_flow_imbalance_signal(FLOWS, field="inst_net", window_days=7)
    # t=08-14: embargo 1 day → 08-14 row excluded, only 08-10, 08-11
    assert fn([_bar("005930", "2026-08-14")]) == (100 - 200) / 4000


def test_window_bound_excludes_old_rows():
    fn = make_flow_imbalance_signal(FLOWS, field="inst_net", window_days=2)
    # t=08-12: window [08-10, 08-11]... window_days=2 → [08-10, 08-11]
    assert fn([_bar("005930", "2026-08-12")]) == (100 - 200) / 4000
    fn1 = make_flow_imbalance_signal(FLOWS, field="inst_net", window_days=1)
    # t=08-12: window [08-11, 08-11] only
    assert fn1([_bar("005930", "2026-08-12")]) == -200 / 3000


def test_smart_field_sums_inst_and_frgn():
    fn = make_flow_imbalance_signal(FLOWS, field="smart", window_days=7)
    assert fn([_bar("005930", "2026-08-15")]) == (100 - 50 - 200 + 150 + 300 + 100) / 6000


def test_no_coverage_returns_none_not_zero():
    fn = make_flow_imbalance_signal(FLOWS, field="inst_net", window_days=7)
    assert fn([_bar("035420", "2026-08-15")]) is None  # symbol not in flow table
    assert fn([]) is None


def test_symbol_dataclass_resolves_to_ticker():
    from trader.core.events import Market, Symbol

    fn = make_flow_imbalance_signal(FLOWS, field="inst_net", window_days=7)
    sym = Symbol(ticker="005930", market=Market.KOSPI, currency="KRW")
    bars = [BarEvent(symbol=sym, ts=_bar("x", "2026-08-15").ts,
                     open=1, high=1, low=1, close=1, volume=100)]
    assert fn(bars) == (100 - 200 + 300) / 6000
