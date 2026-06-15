"""Sentiment cache — score each NewsItem exactly once per (symbol, provider, id)."""
from __future__ import annotations
from datetime import datetime
from typing import Tuple

from trader.signals.news.models import NewsItem, SentimentResult
from trader.signals.news.sentiment import SentimentScorer


class SentimentCache:
    """Cache SentimentResult by (symbol, provider, item.id); call scorer only on cache miss."""

    def __init__(self) -> None:
        self._cache: dict[Tuple[str, str, str], SentimentResult] = {}

    def get_or_score(
        self,
        item: NewsItem,
        scorer: SentimentScorer,
        *,
        symbol: str,
        as_of: datetime,
    ) -> SentimentResult:
        key = (symbol, item.provider, item.id)
        if key not in self._cache:
            self._cache[key] = scorer.score(item, symbol=symbol, as_of=as_of)
        return self._cache[key]
