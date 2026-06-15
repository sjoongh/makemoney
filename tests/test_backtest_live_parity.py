# tests/test_backtest_live_parity.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent, Side
from trader.data.historical_feed import InMemoryDailyFeed
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource
from trader.backtest.engine import BacktestEngine
from trader.live.engine import LiveEngine

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

class RecordingExec(SimulatedExecutionHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.orders=[]
    def submit_order(self, order):
        self.orders.append((order.side, order.quantity)); super().submit_order(order)

def _wire():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":13_000_000.0}, fx)
    eng = FusionEngine([TechnicalSignalSource(2,4)], pf, RiskManager(0.5), OrderFactory(), enter_threshold=0.02)
    ex = RecordingExec(BpsCostModel(0.0))
    return pf, eng, ex

def test_backtest_and_live_produce_identical_orders_and_equity():
    closes = [1,2,3,4,5,6,5,4,5,6,7,8]
    pf1, e1, x1 = _wire(); BacktestEngine(InMemoryDailyFeed(_bars(closes)), e1, x1, pf1).run()
    pf2, e2, x2 = _wire(); LiveEngine(InMemoryDailyFeed(_bars(closes)), e2, x2, pf2).run()
    assert x1.orders == x2.orders                       # 동일 주문 시퀀스
    assert round(pf1.equity_krw()) == round(pf2.equity_krw())  # 동일 최종 자산
