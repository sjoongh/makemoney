"""Frozen dataclasses for news signal pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsItem:
    id: str
    symbol: str
    title: str
    body: str | None
    url: str | None
    published_at: datetime
    provider: str

    def __post_init__(self) -> None:
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")


@dataclass(frozen=True)
class SentimentResult:
    item_id: str
    score: float
    confidence: float
    horizon: str
    event_type: str | None
    rationale: str | None
    model: str

    def __post_init__(self) -> None:
        if not -1.0 <= self.score <= 1.0:
            raise ValueError("score must be in [-1, 1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
