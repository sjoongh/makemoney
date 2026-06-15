"""Tests for trader/signals/news/sentiment.py"""
import pytest
from datetime import datetime, timezone
from trader.signals.news.models import NewsItem
from trader.signals.news.sentiment import MockSentimentScorer, ClaudeSentimentScorer

AS_OF = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _item(title: str, id: str = "n1") -> NewsItem:
    return NewsItem(
        id=id,
        symbol="AAPL",
        title=title,
        body=None,
        url=None,
        published_at=AS_OF,
        provider="mock",
    )


def _score(title: str):
    scorer = MockSentimentScorer()
    return scorer.score(_item(title), symbol="AAPL", as_of=AS_OF)


# --- MockSentimentScorer bullish keywords ---

@pytest.mark.parametrize("title", [
    "Apple beats earnings expectations",
    "Stock surge after results",
    "Market jumps on news",
    "Sets new record high",
    "Analyst upgrade issued",
])
def test_mock_bullish_keywords(title: str):
    r = _score(title)
    assert r.score == 0.7
    assert r.confidence == 0.7


# --- MockSentimentScorer bearish keywords ---

@pytest.mark.parametrize("title", [
    "Apple miss on revenue",
    "Stock plunge after earnings",
    "Share price falls on warning",
    "Analyst downgrade issued",
    "SEC probe announced",
    "Company faces lawsuit over product",
])
def test_mock_bearish_keywords(title: str):
    r = _score(title)
    assert r.score == -0.7
    assert r.confidence == 0.7


# --- MockSentimentScorer neutral ---

@pytest.mark.parametrize("title", [
    "Apple announces new partnership",
    "Company holds annual meeting",
    "No material news today",
])
def test_mock_neutral(title: str):
    r = _score(title)
    assert r.score == 0.0
    assert r.confidence == 0.2


# --- Result metadata ---

def test_mock_result_fields():
    r = _score("Company beats targets")
    assert r.item_id == "n1"
    assert r.horizon == "5d"
    assert r.event_type is None
    assert r.model == "mock"


def test_mock_case_insensitive():
    """Keyword match is case-insensitive (title lowercased before check)."""
    r = _score("Apple BEATS Estimates")
    assert r.score == 0.7


# --- Score/confidence always in valid range ---

def test_mock_score_in_range():
    for title in ["beats", "miss", "neutral text"]:
        r = _score(title)
        assert -1.0 <= r.score <= 1.0
        assert 0.0 <= r.confidence <= 1.0


# --- ClaudeSentimentScorer skeleton ---

def test_claude_scorer_no_client_raises():
    scorer = ClaudeSentimentScorer()
    with pytest.raises(NotImplementedError, match="ANTHROPIC_API_KEY"):
        scorer.score(_item("Apple beats"), symbol="AAPL", as_of=AS_OF)
