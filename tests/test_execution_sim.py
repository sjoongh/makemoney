from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, OrderEvent, Side
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def bar(day, o):
    t = datetime(2026,1,day,tzinfo=timezone.utc)
    return BarEvent(SYM, t, open=o, high=o+1, low=o-1, close=o+0.5, volume=100)

def test_order_fills_at_next_bar_open_not_same_bar():
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    b1, b2 = bar(2, 10.0), bar(3, 12.0)
    assert ex.on_bar(b1) == []                       # 대기 주문 없음
    ex.submit_order(OrderEvent(uuid4(), SYM, b1.ts, Side.BUY, 5))  # b1 종가 후 주문
    fills = ex.on_bar(b2)                              # 다음 봉
    assert len(fills) == 1
    assert fills[0].price == 12.0                      # b2 '시가'에 체결
    assert fills[0].quantity == 5 and fills[0].side == Side.BUY
