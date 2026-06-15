"""Tests for trader/signals/news/models.py"""
import pytest
from datetime import datetime, timezone, timedelta
from trader.signals.news.models import NewsItem, SentimentResult


AWARE_DT = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
NAIVE_DT = datetime(2026, 6, 15, 12, 0, 0)


def _item(**overrides):
    defaults = dict(
        id="n1",
        symbol="AAPL",
        title="Apple beats expectations",
        body="Some body text.",
        url="https://example.com/news/1",
        published_at=AWARE_DT,
        provider="finnhub",
    )
    defaults.update(overrides)
    return NewsItem(**defaults)


def _result(**overrides):
    defaults = dict(
        item_id="n1",
        score=0.5,
        confidence=0.8,
        horizon="5d",
        event_type="earnings",
        rationale="Positive surprise on EPS.",
        model="mock",
    )
    defaults.update(overrides)
    return SentimentResult(**defaults)


# --- NewsItem construction ---

def test_news_item_construction():
    item = _item()
    assert item.id == "n1"
    assert item.symbol == "AAPL"
    assert item.title == "Apple beats expectations"
    assert item.body == "Some body text."
    assert item.url == "https://example.com/news/1"
    assert item.published_at == AWARE_DT
    assert item.provider == "finnhub"


def test_news_item_optional_body_none():
    item = _item(body=None)
    assert item.body is None


def test_news_item_optional_url_none():
    item = _item(url=None)
    assert item.url is None


def test_news_item_immutable():
    item = _item()
    with pytest.raises((AttributeError, TypeError)):
        item.title = "changed"  # type: ignore[misc]


def test_news_item_naive_datetime_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        _item(published_at=NAIVE_DT)


# --- SentimentResult construction ---

def test_sentiment_result_construction():
    r = _result()
    assert r.item_id == "n1"
    assert r.score == 0.5
    assert r.confidence == 0.8
    assert r.horizon == "5d"
    assert r.event_type == "earnings"
    assert r.rationale == "Positive surprise on EPS."
    assert r.model == "mock"


def test_sentiment_result_optional_event_type_none():
    r = _result(event_type=None)
    assert r.event_type is None


def test_sentiment_result_optional_rationale_none():
    r = _result(rationale=None)
    assert r.rationale is None


def test_sentiment_result_immutable():
    r = _result()
    with pytest.raises((AttributeError, TypeError)):
        r.score = 0.0  # type: ignore[misc]


def test_sentiment_result_score_boundary_valid():
    # exact boundaries must be accepted
    _result(score=-1.0)
    _result(score=0.0)
    _result(score=1.0)


def test_sentiment_result_score_too_high():
    with pytest.raises(ValueError, match="score"):
        _result(score=1.1)


def test_sentiment_result_score_too_low():
    with pytest.raises(ValueError, match="score"):
        _result(score=-1.1)


def test_sentiment_result_confidence_boundary_valid():
    _result(confidence=0.0)
    _result(confidence=1.0)


def test_sentiment_result_confidence_too_high():
    with pytest.raises(ValueError, match="confidence"):
        _result(confidence=1.01)


def test_sentiment_result_confidence_negative():
    with pytest.raises(ValueError, match="confidence"):
        _result(confidence=-0.1)
