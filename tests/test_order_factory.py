# tests/test_order_factory.py
from datetime import datetime, timezone
from trader.core.events import Symbol, Market, TargetPosition, Side
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.order_factory import OrderFactory

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(): return datetime(2026,1,3,tzinfo=timezone.utc)

def test_target_weight_to_integer_buy():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    p = Portfolio(cash={"KRW":13_000_000.0}, fx=fx)   # equity=1300만, 포지션 0
    of = OrderFactory()
    # 목표 50% → 650만원 / (100*1300=13만/주) = 50주
    orders = of.orders_for_target(TargetPosition(SYM, 0.5), p, price=100.0, ts=_t())
    assert len(orders) == 1 and orders[0].side == Side.BUY and orders[0].quantity == 50

def test_no_order_when_delta_zero():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    p = Portfolio(cash={"KRW":0.0}, fx=fx)
    of = OrderFactory()
    assert of.orders_for_target(TargetPosition(SYM, 0.0), p, price=100.0, ts=_t()) == []
