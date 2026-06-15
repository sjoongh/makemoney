# tests/test_historical_feed.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.data.historical_feed import InMemoryDailyFeed

def _bar(sym, day, c):
    t = datetime(2026,1,day,tzinfo=timezone.utc)
    return BarEvent(sym, t, c, c, c, c, 100)

def test_feed_yields_in_timestamp_order_across_symbols():
    a = Symbol("AAPL", Market.NASDAQ, "USD"); k = Symbol("005930", Market.KOSPI, "KRW")
    bars = [_bar(a,3,3),_bar(k,2,2),_bar(a,2,2.5),_bar(k,3,3.5)]
    feed = InMemoryDailyFeed(bars)
    out = list(feed.events())
    assert [b.ts for b in out] == sorted(b.ts for b in out)
    assert len(out) == 4
