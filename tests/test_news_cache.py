"""Tests for trader/signals/news/cache.py"""
from datetime import datetime, timezone
from trader.signals.news.models import NewsItem, SentimentResult
from trader.signals.news.cache import SentimentCache

AS_OF = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _item(id: str, title: str = "neutral") -> NewsItem:
    return NewsItem(
        id=id,
        symbol="AAPL",
        title=title,
        body=None,
        url=None,
        published_at=AS_OF,
        provider="mock",
    )


def _result(item_id: str, score: float = 0.5) -> SentimentResult:
    return SentimentResult(
        item_id=item_id,
        score=score,
        confidence=0.7,
        horizon="5d",
        event_type=None,
        rationale=None,
        model="mock",
    )


class CountingFakeScorer:
    """Records how many times score() is called per item id."""

    def __init__(self) -> None:
        self.call_count: dict[str, int] = {}

    def score(self, item: NewsItem, *, symbol: str, as_of: datetime) -> SentimentResult:
        self.call_count[item.id] = self.call_count.get(item.id, 0) + 1
        return _result(item.id)


def test_cache_calls_scorer_once_for_same_item():
    """score() must be called exactly once even when same item fetched twice."""
    cache = SentimentCache()
    scorer = CountingFakeScorer()
    item = _item("n1")

    r1 = cache.get_or_score(item, scorer, symbol="AAPL", as_of=AS_OF)
    r2 = cache.get_or_score(item, scorer, symbol="AAPL", as_of=AS_OF)

    assert scorer.call_count["n1"] == 1
    assert r1 is r2  # same object returned from cache


def test_cache_returns_correct_result():
    cache = SentimentCache()
    scorer = CountingFakeScorer()
    item = _item("n2")

    result = cache.get_or_score(item, scorer, symbol="AAPL", as_of=AS_OF)
    assert result.item_id == "n2"


def test_cache_scores_different_items_separately():
    """Each distinct item.id must be scored independently."""
    cache = SentimentCache()
    scorer = CountingFakeScorer()
    item_a = _item("a")
    item_b = _item("b")

    cache.get_or_score(item_a, scorer, symbol="AAPL", as_of=AS_OF)
    cache.get_or_score(item_a, scorer, symbol="AAPL", as_of=AS_OF)
    cache.get_or_score(item_b, scorer, symbol="AAPL", as_of=AS_OF)
    cache.get_or_score(item_b, scorer, symbol="AAPL", as_of=AS_OF)

    assert scorer.call_count["a"] == 1
    assert scorer.call_count["b"] == 1


def test_cache_hit_does_not_invoke_scorer_again():
    """Explicitly confirm scorer is NOT called on second request."""
    cache = SentimentCache()
    scorer = CountingFakeScorer()
    item = _item("n3")

    cache.get_or_score(item, scorer, symbol="AAPL", as_of=AS_OF)
    assert scorer.call_count.get("n3", 0) == 1

    # second call — must NOT increment counter
    cache.get_or_score(item, scorer, symbol="AAPL", as_of=AS_OF)
    assert scorer.call_count["n3"] == 1
