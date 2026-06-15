# tests/test_fusion_engine.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent, Side
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

def _engine():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    return FusionEngine([TechnicalSignalSource(2,4)],
                        Portfolio({"KRW":13_000_000.0}, fx),
                        RiskManager(0.5), OrderFactory(),
                        enter_threshold=0.05)

def test_uptrend_produces_buy_order():
    eng = _engine(); orders = []
    for b in _bars([1,2,3,4,5,6]): orders = eng.on_bar(b) or orders
    assert any(o.side == Side.BUY for o in orders)

def test_same_inputs_same_orders_determinism():
    seq = _bars([1,2,3,4,5,6])
    a = _engine(); b = _engine()
    out_a = [eng_out for x in seq for eng_out in a.on_bar(x)]
    out_b = [eng_out for x in seq for eng_out in b.on_bar(x)]
    assert [(o.side,o.quantity) for o in out_a] == [(o.side,o.quantity) for o in out_b]
