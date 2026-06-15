# tests/test_backtest_engine.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.data.historical_feed import InMemoryDailyFeed
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource
from trader.backtest.engine import BacktestEngine

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

def _wire():
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":13_000_000.0}, fx)
    eng = FusionEngine([TechnicalSignalSource(2,4)], pf, RiskManager(0.5), OrderFactory(), enter_threshold=0.02)
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    return pf, eng, ex

def test_backtest_runs_and_takes_a_position():
    pf, eng, ex = _wire()
    feed = InMemoryDailyFeed(_bars([1,2,3,4,5,6,7,8]))
    BacktestEngine(feed, eng, ex, pf).run()
    assert pf.position(SYM) > 0          # 상승추세에서 매수 진입
    assert pf.equity_krw() > 0
