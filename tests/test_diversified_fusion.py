# tests/test_diversified_fusion.py
"""Integration test: 4 diversified TechnicalIndicatorSource instances fused via
FusionEngine + LiveEngine + InMemoryDailyFeed + SimulatedExecution.

Verifies that the wired-up diversified source set produces at least one order
given a rising bar series long enough to warm all indicators (slow=30 for MA,
slow=26+signal=9=35 for MACD → need 35+ bars).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from trader.core.events import BarEvent, Market, Symbol
from trader.data.historical_feed import InMemoryDailyFeed
from trader.execution.costs import BpsCostModel
from trader.execution.simulated import SimulatedExecutionHandler
from trader.signals.indicators import (
    BollingerReversion,
    MacdTrend,
    MovingAverageCross,
    RsiReversion,
)
from trader.signals.technical_indicator_source import TechnicalIndicatorSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager
from trader.live.engine import LiveEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _bars(closes: list[float]) -> list[BarEvent]:
    return [
        BarEvent(SYM, T0 + timedelta(days=i), c, c, c, c, 1000)
        for i, c in enumerate(closes)
    ]


def _diversified_sources() -> list[TechnicalIndicatorSource]:
    return [
        TechnicalIndicatorSource(name="technical.ma_10_30",  indicator=MovingAverageCross(10, 30)),
        TechnicalIndicatorSource(name="technical.rsi_14",    indicator=RsiReversion(14, 30, 70)),
        TechnicalIndicatorSource(name="technical.macd",      indicator=MacdTrend(12, 26, 9)),
        TechnicalIndicatorSource(name="technical.boll_20_2", indicator=BollingerReversion(20, 2.0)),
    ]


SOURCE_WEIGHT = {
    "technical.ma_10_30":  0.30,
    "technical.rsi_14":    0.20,
    "technical.macd":      0.30,
    "technical.boll_20_2": 0.20,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiversifiedFusion:

    def test_diversified_sources_produce_at_least_one_order(self):
        """Full pipeline: rising bar series → at least one BUY order is emitted."""
        # 50 bars rising steadily — enough to warm MA(slow=30), MACD(26+9=35), RSI(15), BB(20)
        closes = [10.0 + i * 0.5 for i in range(50)]

        fx = FxRates({"USD": 1300.0, "KRW": 1.0})
        pf = Portfolio({"KRW": 13_000_000.0}, fx)
        sources = _diversified_sources()
        eng = FusionEngine(
            sources,
            pf,
            RiskManager(0.3),
            OrderFactory(),
            enter_threshold=0.02,   # low threshold to ensure orders fire in test
            source_weight=SOURCE_WEIGHT,
        )
        ex = SimulatedExecutionHandler(BpsCostModel(0.0))
        feed = InMemoryDailyFeed(_bars(closes))

        # Track orders via a recording wrapper
        orders_seen: list = []
        original_submit = ex.submit_order

        def recording_submit(order):
            orders_seen.append(order)
            original_submit(order)

        ex.submit_order = recording_submit  # type: ignore[method-assign]

        LiveEngine(feed, eng, ex, pf).run()

        assert len(orders_seen) >= 1, (
            f"Expected at least 1 order from diversified fusion, got {len(orders_seen)}"
        )

    def test_diversified_sources_complete_without_error(self):
        """Pipeline runs to completion without raising."""
        closes = [10.0 + i * 0.3 for i in range(60)]
        fx = FxRates({"USD": 1300.0, "KRW": 1.0})
        pf = Portfolio({"KRW": 13_000_000.0}, fx)
        sources = _diversified_sources()
        eng = FusionEngine(sources, pf, RiskManager(0.3), OrderFactory(),
                           enter_threshold=0.35, source_weight=SOURCE_WEIGHT)
        ex = SimulatedExecutionHandler(BpsCostModel(0.0))
        LiveEngine(InMemoryDailyFeed(_bars(closes)), eng, ex, pf).run()
        # If we reach here without exception, the test passes.

    def test_each_source_has_correct_name(self):
        """Source names match the expected weighted-fusion keys."""
        sources = _diversified_sources()
        names = {s.name for s in sources}
        assert names == set(SOURCE_WEIGHT.keys())

    def test_each_source_supports_backtest(self):
        for src in _diversified_sources():
            assert src.supports_backtest is True, f"{src.name} must support backtest"

    def test_warmup_only_returns_none_signals(self):
        """During the first min_bars bars, no signals are emitted by any source."""
        # Use only 10 bars — well below any indicator's min_bars (RSI needs 15, MA needs 30…)
        closes = [float(i + 1) for i in range(10)]
        bars = _bars(closes)
        sources = _diversified_sources()
        for src in sources:
            for bar in bars:
                result = src.on_bar(bar)
                assert result is None, (
                    f"Source {src.name} emitted signal during warmup at bar {bar.ts}"
                )
