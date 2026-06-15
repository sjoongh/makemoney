# tests/test_phase2_integration.py
"""Phase 2 integration tests: news source in live path + backtest guard."""
from __future__ import annotations

import pytest
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
from trader.signals.news.source import NewsSignalSource
from trader.signals.news.providers import MockNewsProvider
from trader.signals.news.sentiment import MockSentimentScorer
from trader.signals.news.models import NewsItem
from trader.backtest.engine import BacktestEngine
from trader.live.engine import LiveEngine

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _bars(closes: list[float]) -> list[BarEvent]:
    return [BarEvent(SYM, T0 + timedelta(days=i), c, c, c, c, 100)
            for i, c in enumerate(closes)]


def _news_items() -> list[NewsItem]:
    """One bullish item ('beats') dated at bar 0 — within the lookback window."""
    return [
        NewsItem(
            id="n1",
            symbol="AAPL",
            title="AAPL beats earnings expectations",
            body=None,
            url=None,
            published_at=T0,
            provider="mock",
        )
    ]


def test_fusion_with_news_source_runs_in_live_engine():
    """FusionEngine with both TechnicalSignalSource and NewsSignalSource
    runs through LiveEngine without error and takes a long position on a
    rising price series where news also contributes a bullish signal."""
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 13_000_000.0}, fx)
    news = NewsSignalSource(MockNewsProvider(_news_items()), MockSentimentScorer())
    eng = FusionEngine(
        [TechnicalSignalSource(2, 4), news],
        pf,
        RiskManager(0.5),
        OrderFactory(),
        enter_threshold=0.02,
        source_weight={"technical": 1.0, "news_llm": 0.5},
    )
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    feed = InMemoryDailyFeed(_bars([1, 2, 3, 4, 5, 6, 7, 8]))

    LiveEngine(feed, eng, ex, pf).run()

    # Rising series + bullish news → must take a long position
    assert pf.position(SYM) > 0, "expected a long position after rising series with bullish news"
    assert pf.equity_krw() > 0


def test_backtest_rejects_news_source():
    """BacktestEngine must raise ValueError for any live-only signal source."""
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 13_000_000.0}, fx)
    news = NewsSignalSource(MockNewsProvider([]), MockSentimentScorer())
    eng = FusionEngine(
        [TechnicalSignalSource(2, 4), news],
        pf,
        RiskManager(0.5),
        OrderFactory(),
    )
    ex = SimulatedExecutionHandler(BpsCostModel(0.0))
    feed = InMemoryDailyFeed(_bars([1, 2, 3, 4, 5]))

    with pytest.raises(ValueError, match="live-only signal source 'news_llm' cannot be used in backtest"):
        BacktestEngine(feed, eng, ex, pf)
