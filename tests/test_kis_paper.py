# tests/test_kis_paper.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, OrderEvent, Side
from trader.execution.kis_paper import KisPaperExecutionHandler

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(d=2): return datetime(2026,1,d,tzinfo=timezone.utc)

class FakeKis:
    def __init__(self): self.submitted=[]; self._fill_next=False
    def submit_order(self, ticker, market, side, quantity):
        self.submitted.append((ticker, side, quantity)); self._fill_next=True; return "OID1"
    def filled_orders(self):
        if self._fill_next:
            self._fill_next=False
            return [{"order_id":"OID1","ticker":"AAPL","market":"NASDAQ","currency":"USD",
                     "side":"BUY","qty":5,"price":12.0,"commission":0.1}]
        return []

def test_repeated_filled_orders_apply_only_once():
    from datetime import datetime, timezone
    from uuid import uuid4
    from trader.core.events import Symbol, Market, BarEvent, OrderEvent, Side
    from trader.execution.kis_paper import KisPaperExecutionHandler
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    def t(d): return datetime(2026,1,d,tzinfo=timezone.utc)
    class StickyKis:
        def submit_order(self, ticker, market, side, quantity): return "OID1"
        def filled_orders(self):
            return [{"order_id":"OID1","ticker":"AAPL","market":"NASDAQ","currency":"USD",
                     "side":"BUY","qty":5,"price":12.0,"commission":0.1}]  # 매 폴링 동일 반환
    kis = StickyKis(); ex = KisPaperExecutionHandler(kis)
    ex.submit_order(OrderEvent(uuid4(), sym, t(2), Side.BUY, 5))
    f1 = ex.on_bar(BarEvent(sym,t(3),12,12,12,12,1))
    f2 = ex.on_bar(BarEvent(sym,t(4),13,13,13,13,1))
    assert len(f1) == 1 and len(f2) == 0   # 같은 체결은 한 번만

def test_submit_then_reconcile_fill_on_next_bar():
    kis = FakeKis(); ex = KisPaperExecutionHandler(kis)
    assert ex.on_bar(BarEvent(SYM,_t(2),10,10,10,10,1)) == []
    ex.submit_order(OrderEvent(uuid4(), SYM, _t(2), Side.BUY, 5))
    assert kis.submitted == [("AAPL","BUY",5)]
    fills = ex.on_bar(BarEvent(SYM,_t(3),12,12,12,12,1))
    assert len(fills)==1 and fills[0].price==12.0 and fills[0].quantity==5
