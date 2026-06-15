from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, OrderEvent, Side
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
OTHER = Symbol("MSFT", Market.NASDAQ, "USD")
def bar(day, o, sym=SYM):
    t = datetime(2026,1,day,tzinfo=timezone.utc)
    return BarEvent(sym, t, open=o, high=o+1, low=o-1, close=o+0.5, volume=100)

def test_order_fills_at_next_bar_open_not_same_bar():
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    b1, b2 = bar(2, 10.0), bar(3, 12.0)
    assert ex.on_bar(b1) == []                       # 대기 주문 없음
    ex.submit_order(OrderEvent(uuid4(), SYM, b1.ts, Side.BUY, 5))  # b1 종가 후 주문
    fills = ex.on_bar(b2)                              # 다음 봉
    assert len(fills) == 1
    assert fills[0].price == 12.0                      # b2 '시가'에 체결
    assert fills[0].quantity == 5 and fills[0].side == Side.BUY

def test_order_for_unreprinted_symbol_never_fills():
    """심볼이 재출현하지 않으면 주문은 체결을 만들지 않는다(유령 미래 체결 금지)."""
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    ex.submit_order(OrderEvent(uuid4(), SYM, bar(2, 10.0).ts, Side.BUY, 5))
    # 이후 다른 심볼 봉만 도착 → AAPL 주문은 체결되지 않음
    assert ex.on_bar(bar(3, 20.0, OTHER)) == []
    assert ex.on_bar(bar(4, 21.0, OTHER)) == []
