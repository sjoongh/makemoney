# tests/test_clock.py
from datetime import datetime, timezone
from trader.core.clock import BacktestClock
from trader.data.calendar import trading_days

def test_backtest_clock_returns_injected_time():
    t = datetime(2026, 1, 2, tzinfo=timezone.utc)
    c = BacktestClock(); c.set(t)
    assert c.now() == t

def test_trading_days_are_ordered_and_weekday_only():
    days = trading_days(datetime(2026,1,1,tzinfo=timezone.utc), datetime(2026,1,8,tzinfo=timezone.utc))
    assert days == sorted(days)
    assert all(d.weekday() < 5 for d in days)
