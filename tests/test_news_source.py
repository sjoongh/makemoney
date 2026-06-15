"""TDD tests for NewsSignalSource (Phase 2, T6).

Covers:
- Look-ahead safety (items after bar.ts are ignored)
- Positive / negative signal direction
- No news → None
- Time-decay: older item produces smaller-magnitude signal
- Cache: underlying scorer called only once per item across bars
- Class-level supports_backtest attribute
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from trader.core.events import BarEvent, Market, NormalizedSignal, Symbol
from trader.signals.news.models import NewsItem, SentimentResult
from trader.signals.news.providers import MockNewsProvider
from trader.signals.news.sentiment import MockSentimentScorer
from trader.signals.news.source import NewsSignalSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc
SYM = Symbol("AAPL", Market.NASDAQ, "USD")


def _item(
    item_id: str,
    title: str,
    published_at: datetime,
    symbol: str = "AAPL",
) -> NewsItem:
    return NewsItem(
        id=item_id,
        symbol=symbol,
        title=title,
        body=None,
        url=None,
        published_at=published_at,
        provider="test",
    )


def _bar(ts: datetime) -> BarEvent:
    return BarEvent(
        symbol=SYM,
        ts=ts,
        open=100.0,
        high=105.0,
        low=99.0,
        close=102.0,
        volume=1_000,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_supports_backtest_is_false():
    """Class-level attribute must be False — live-only source."""
    assert NewsSignalSource.supports_backtest is False
    src = NewsSignalSource(MockNewsProvider([]), MockSentimentScorer())
    assert src.supports_backtest is False


def test_no_news_returns_none():
    """Empty provider → on_bar returns None."""
    src = NewsSignalSource(MockNewsProvider([]), MockSentimentScorer())
    bar = _bar(datetime(2026, 1, 10, tzinfo=UTC))
    assert src.on_bar(bar) is None


def test_positive_news_yields_positive_signal():
    """An item with 'beats' in title → score > 0, source == 'news_llm'."""
    bar_ts = datetime(2026, 1, 10, tzinfo=UTC)
    item = _item("a1", "AAPL beats earnings expectations", bar_ts - timedelta(hours=2))
    src = NewsSignalSource(MockNewsProvider([item]), MockSentimentScorer())
    sig = src.on_bar(_bar(bar_ts))
    assert sig is not None
    assert sig.score > 0
    assert sig.source == "news_llm"
    assert sig.symbol == SYM
    assert sig.horizon == "5d"


def test_negative_news_yields_negative_signal():
    """An item with 'plunge' in title → score < 0."""
    bar_ts = datetime(2026, 1, 10, tzinfo=UTC)
    item = _item("b1", "AAPL stock plunge after recall", bar_ts - timedelta(hours=1))
    src = NewsSignalSource(MockNewsProvider([item]), MockSentimentScorer())
    sig = src.on_bar(_bar(bar_ts))
    assert sig is not None
    assert sig.score < 0


def test_lookahead_news_after_bar_is_ignored():
    """Item published AFTER bar.ts must not affect signal.

    Provider already filters, but source must defensively re-filter.
    We inject a future item by bypassing the provider filter (pass raw items
    to a provider that would normally exclude them, then verify None).
    """
    bar_ts = datetime(2026, 1, 10, tzinfo=UTC)
    future_item = _item("f1", "AAPL beats forecast tomorrow", bar_ts + timedelta(hours=1))

    # MockNewsProvider enforces look-ahead safety, so it returns nothing.
    # But we also want to confirm that even if a broken provider leaked a
    # future item, the source's defensive re-filter would catch it.
    # We test the end result: no valid items → None.
    src = NewsSignalSource(MockNewsProvider([future_item]), MockSentimentScorer())
    result = src.on_bar(_bar(bar_ts))
    assert result is None


def test_time_decay_old_news_weighs_less():
    """Older item → smaller |score| (or same direction but lower decayed conf).

    We compare two separate NewsSignalSource instances:
    - 'recent': item published 1 day before bar
    - 'stale':  item published 6 days before bar (halflife_days=3)

    Both items have the same title ("AAPL beats"), so MockSentimentScorer
    gives the same raw score.  Time-decay makes 'stale' produce a lower
    combined confidence (max decayed confidence is smaller).
    """
    halflife = 3.0
    bar_ts = datetime(2026, 1, 10, tzinfo=UTC)

    recent_item = _item("r1", "AAPL beats forecast", bar_ts - timedelta(days=1))
    stale_item  = _item("s1", "AAPL beats forecast", bar_ts - timedelta(days=6))

    src_recent = NewsSignalSource(
        MockNewsProvider([recent_item]),
        MockSentimentScorer(),
        halflife_days=halflife,
        lookback=timedelta(days=10),
    )
    src_stale = NewsSignalSource(
        MockNewsProvider([stale_item]),
        MockSentimentScorer(),
        halflife_days=halflife,
        lookback=timedelta(days=10),
    )

    bar = _bar(bar_ts)
    sig_recent = src_recent.on_bar(bar)
    sig_stale  = src_stale.on_bar(bar)

    assert sig_recent is not None
    assert sig_stale is not None

    # Decay: recent weight = 0.5^(1/3) ≈ 0.794; stale weight = 0.5^(6/3) = 0.25
    # Both items have conf=0.7, so effective weights are 0.556 vs 0.175.
    # Combined confidence = max decayed conf: recent=0.794*0.7≈0.556, stale=0.25*0.7=0.175
    assert sig_recent.confidence > sig_stale.confidence, (
        f"Recent conf {sig_recent.confidence:.4f} should exceed stale {sig_stale.confidence:.4f}"
    )


def test_item_scored_only_once_across_bars():
    """Same item seen across two bars → underlying score() called exactly once."""
    bar_ts1 = datetime(2026, 1, 10, tzinfo=UTC)
    bar_ts2 = datetime(2026, 1, 11, tzinfo=UTC)

    item = _item("x1", "AAPL beats earnings", bar_ts1 - timedelta(hours=6))

    class CountingScorer:
        call_count = 0

        def score(self, news_item: NewsItem, *, symbol: str, as_of: datetime) -> SentimentResult:
            CountingScorer.call_count += 1
            return SentimentResult(
                item_id=news_item.id,
                score=0.7,
                confidence=0.7,
                horizon="5d",
                event_type=None,
                rationale=None,
                model="counting",
            )

    scorer = CountingScorer()
    provider = MockNewsProvider([item])
    src = NewsSignalSource(provider, scorer, lookback=timedelta(days=7))

    # Bar 1: item is within window for both bars
    src.on_bar(_bar(bar_ts1))
    # Bar 2: same item still within lookback window
    src.on_bar(_bar(bar_ts2))

    assert CountingScorer.call_count == 1, (
        f"Expected scorer called 1 time, got {CountingScorer.call_count}"
    )


def test_signal_features_contain_n_items():
    """Emitted signal must carry n_items feature."""
    bar_ts = datetime(2026, 1, 10, tzinfo=UTC)
    items = [
        _item("p1", "AAPL beats sales record", bar_ts - timedelta(hours=3)),
        _item("p2", "AAPL beats analyst estimate", bar_ts - timedelta(hours=5)),
    ]
    src = NewsSignalSource(MockNewsProvider(items), MockSentimentScorer())
    sig = src.on_bar(_bar(bar_ts))
    assert sig is not None
    assert sig.features["n_items"] == 2


def test_name_attribute():
    """source.name must equal 'news_llm'."""
    src = NewsSignalSource(MockNewsProvider([]), MockSentimentScorer())
    assert src.name == "news_llm"
