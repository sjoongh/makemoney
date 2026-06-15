# tests/test_kis_live_feed.py
from trader.data.kis_live_feed import KisLiveFeed
from trader.core.events import BarEvent, Symbol, Market
from datetime import datetime, timezone

class FakeKis:
    def daily_bars(self, ticker, market, currency):
        return [BarEvent(Symbol(ticker, Market(market), currency),
                         datetime(2026,1,2,tzinfo=timezone.utc), 1,1,1,1,1)]

def test_live_feed_yields_canonical_bars():
    feed = KisLiveFeed(FakeKis(), [("AAPL","NASDAQ","USD")])
    bars = list(feed.events())
    assert len(bars) == 1 and isinstance(bars[0], BarEvent)
