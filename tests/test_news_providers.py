"""Tests for trader/signals/news/providers.py"""
import pytest
from datetime import datetime, timezone, timedelta
from trader.signals.news.models import NewsItem
from trader.signals.news.providers import MockNewsProvider, LiveFinnhubProvider, LiveDartProvider


def _dt(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 6, day, hour, 0, 0, tzinfo=timezone.utc)


def _item(id: str, symbol: str, published_at: datetime) -> NewsItem:
    return NewsItem(
        id=id,
        symbol=symbol,
        title=f"News {id}",
        body=None,
        url=None,
        published_at=published_at,
        provider="mock",
    )


AS_OF = _dt(15)  # 2026-06-15 12:00 UTC
LOOKBACK = timedelta(days=5)  # earliest = 2026-06-10 12:00 UTC


def _provider() -> MockNewsProvider:
    items = [
        _item("old", "AAPL", _dt(9)),    # too old — before lookback window
        _item("a", "AAPL", _dt(10)),     # exactly at earliest boundary — included
        _item("b", "AAPL", _dt(12)),     # within window
        _item("c", "AAPL", _dt(14)),     # within window
        _item("now", "AAPL", AS_OF),     # exactly as_of — included
        _item("future", "AAPL", _dt(16)),  # AFTER as_of — look-ahead, EXCLUDED
        _item("other", "MSFT", _dt(13)),   # different symbol — excluded
    ]
    return MockNewsProvider(items)


def test_mock_excludes_future_items():
    """Items published AFTER as_of must never be returned (look-ahead guard)."""
    provider = _provider()
    results = provider.fetch_as_of("AAPL", AS_OF, LOOKBACK)
    ids = [r.id for r in results]
    assert "future" not in ids


def test_mock_excludes_items_before_lookback():
    """Items older than as_of - lookback are excluded."""
    provider = _provider()
    results = provider.fetch_as_of("AAPL", AS_OF, LOOKBACK)
    ids = [r.id for r in results]
    assert "old" not in ids


def test_mock_includes_boundary_items():
    """Items at exactly as_of - lookback and as_of are both included."""
    provider = _provider()
    results = provider.fetch_as_of("AAPL", AS_OF, LOOKBACK)
    ids = [r.id for r in results]
    assert "a" in ids    # at earliest boundary
    assert "now" in ids  # at as_of boundary


def test_mock_returns_ascending_order():
    """Results must be sorted ascending by published_at."""
    provider = _provider()
    results = provider.fetch_as_of("AAPL", AS_OF, LOOKBACK)
    timestamps = [r.published_at for r in results]
    assert timestamps == sorted(timestamps)


def test_mock_filters_by_symbol():
    """Results must only contain items for the requested symbol."""
    provider = _provider()
    results = provider.fetch_as_of("AAPL", AS_OF, LOOKBACK)
    assert all(r.symbol == "AAPL" for r in results)
    assert not any(r.symbol == "MSFT" for r in results)


def test_mock_within_window_items_present():
    """Items b and c inside the window are returned."""
    provider = _provider()
    results = provider.fetch_as_of("AAPL", AS_OF, LOOKBACK)
    ids = [r.id for r in results]
    assert "b" in ids
    assert "c" in ids


def test_mock_empty_when_no_items_in_window():
    provider = MockNewsProvider([_item("x", "AAPL", _dt(1))])
    results = provider.fetch_as_of("AAPL", AS_OF, LOOKBACK)
    assert results == []


def test_live_finnhub_raises_not_implemented():
    p = LiveFinnhubProvider(api_key="fake")
    with pytest.raises(NotImplementedError, match="live provider pending API key"):
        p.fetch_as_of("AAPL", AS_OF, LOOKBACK)


def test_live_dart_raises_not_implemented():
    p = LiveDartProvider(api_key="fake")
    with pytest.raises(NotImplementedError, match="live provider pending API key"):
        p.fetch_as_of("AAPL", AS_OF, LOOKBACK)
