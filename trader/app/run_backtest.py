# trader/app/run_backtest.py
from __future__ import annotations
import os
from trader.data.storage import load_bars
from trader.data.historical_feed import InMemoryDailyFeed
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import MarketCostModel
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource
from trader.backtest.engine import BacktestEngine
from trader.backtest.report import print_report
from trader.data.manifest import load_manifest, print_manifest_stamp

def main(parquet_path: str) -> None:
    bars = load_bars(parquet_path)

    # Stamp which dataset + code produced this result
    manifest_path = parquet_path + ".manifest.json"
    if os.path.exists(manifest_path):
        try:
            m = load_manifest(manifest_path)
            print_manifest_stamp(m, bars)
            print()
        except Exception as exc:
            print(f"[MANIFEST] Could not load sidecar: {exc}")

    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":10_000_000.0}, fx)
    eng = FusionEngine([TechnicalSignalSource(20,50)], pf, RiskManager(0.3), OrderFactory())
    ex = SimulatedExecutionHandler(MarketCostModel())
    curve: list[float] = []
    feed = InMemoryDailyFeed(bars)
    class _Track(BacktestEngine):
        def run(self):
            for bar in self.feed.events():
                for fill in self.execution.on_bar(bar): self.strategy.on_fill(fill)
                self.portfolio.mark(bar)
                for o in self.strategy.on_bar(bar): self.execution.submit_order(o)
                curve.append(self.portfolio.equity_krw())
    _Track(feed, eng, ex, pf).run()
    print_report(curve, pf.equity_krw())

if __name__ == "__main__":
    import sys; main(sys.argv[1])
