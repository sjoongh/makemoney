"""Sentiment cache — score each NewsItem exactly once by item.id."""
from __future__ import annotations
from datetime import datetime

from trader.signals.news.models import NewsItem, SentimentResult
from trader.signals.news.sentiment import SentimentScorer


class SentimentCache:
    """Cache SentimentResult by item.id; call scorer only on cache miss."""

    def __init__(self) -> None:
        self._cache: dict[str, SentimentResult] = {}

    def get_or_score(
        self,
        item: NewsItem,
        scorer: SentimentScorer,
        *,
        symbol: str,
        as_of: datetime,
    ) -> SentimentResult:
        if item.id not in self._cache:
            self._cache[item.id] = scorer.score(item, symbol=symbol, as_of=as_of)
        return self._cache[item.id]
