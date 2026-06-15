# tests/test_interfaces.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, OrderEvent, FillEvent, Side
from trader.data.interfaces import DataFeed
from trader.execution.interfaces import ExecutionHandler

SYM = Symbol("AAPL", Market.NASDAQ, "USD")

class FakeFeed:
    def __init__(self, bars): self._bars = bars
    def events(self): return iter(self._bars)

class FakeExec:
    def __init__(self): self.queued = []
    def submit_order(self, order): self.queued.append(order)
    def on_bar(self, bar): return []

def test_fakes_satisfy_protocols():
    bar = BarEvent(SYM, datetime(2026,1,2,tzinfo=timezone.utc),1,1,1,1,1)
    feed: DataFeed = FakeFeed([bar])
    ex: ExecutionHandler = FakeExec()
    assert next(feed.events()) is bar
    ex.submit_order(OrderEvent(uuid4(), SYM, bar.ts, Side.BUY, 1))
    assert ex.on_bar(bar) == [] and len(ex.queued) == 1
