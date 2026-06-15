# tests/test_events.py
import pytest
from datetime import datetime, timezone
from trader.core.events import Market, Side, Symbol, BarEvent, NormalizedSignal

def _ts(): return datetime(2026, 1, 2, tzinfo=timezone.utc)

def test_symbol_and_bar_are_immutable():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    bar = BarEvent(sym, _ts(), 10.0, 11.0, 9.5, 10.5, 1000)
    assert bar.is_closed and bar.timeframe == "1d"
    with pytest.raises(Exception):
        bar.close = 99  # frozen

def test_normalized_signal_rejects_out_of_range():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    with pytest.raises(ValueError):
        NormalizedSignal("technical", sym, _ts(), score=2.0, confidence=0.5, horizon="1d", features={})
    with pytest.raises(ValueError):
        NormalizedSignal("technical", sym, _ts(), score=0.1, confidence=1.5, horizon="1d", features={})

def test_bar_ts_must_be_timezone_aware():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    with pytest.raises(ValueError):
        BarEvent(sym, datetime(2026, 1, 2), 1, 1, 1, 1, 1)  # naive
