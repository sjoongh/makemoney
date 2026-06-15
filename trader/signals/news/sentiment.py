"""Sentiment scorer protocol and implementations."""
from __future__ import annotations
from datetime import datetime
from typing import Protocol

from trader.signals.news.models import NewsItem, SentimentResult

# Keyword sets for MockSentimentScorer
_BULLISH_KEYWORDS = {"beats", "surge", "jumps", "record", "upgrade"}
_BEARISH_KEYWORDS = {"miss", "plunge", "falls", "downgrade", "probe", "lawsuit"}


class SentimentScorer(Protocol):
    def score(
        self, item: NewsItem, *, symbol: str, as_of: datetime
    ) -> SentimentResult:
        ...


class MockSentimentScorer:
    """Deterministic rule-based scorer for testing.

    Title (lowercased) checked for keyword presence:
      - Any of {beats, surge, jumps, record, upgrade}  → score +0.7, conf 0.7
      - Any of {miss, plunge, falls, downgrade, probe, lawsuit} → score -0.7, conf 0.7
      - Otherwise → score 0.0, conf 0.2
    horizon="5d", event_type=None, model="mock"
    """

    def score(
        self, item: NewsItem, *, symbol: str, as_of: datetime
    ) -> SentimentResult:
        lower = item.title.lower()
        if any(kw in lower for kw in _BULLISH_KEYWORDS):
            score, conf = 0.7, 0.7
        elif any(kw in lower for kw in _BEARISH_KEYWORDS):
            score, conf = -0.7, 0.7
        else:
            score, conf = 0.0, 0.2
        return SentimentResult(
            item_id=item.id,
            score=score,
            confidence=conf,
            horizon="5d",
            event_type=None,
            rationale=None,
            model="mock",
        )


class ClaudeSentimentScorer:
    """Claude-backed sentiment scorer — skeleton pending ANTHROPIC_API_KEY.

    TODO: wire to Anthropic SDK once ANTHROPIC_API_KEY is available.
    Pass a real anthropic.Anthropic client via the `client` kwarg,
    and supply system_prompt / build_user_message from prompts.py.
    """

    def __init__(
        self,
        client=None,
        system_prompt: str = "",
        build_user_message=None,
        model: str = "claude-opus-4-8",
    ) -> None:
        self._client = client
        self._system_prompt = system_prompt
        self._build_user_message = build_user_message
        self._model = model

    def score(
        self, item: NewsItem, *, symbol: str, as_of: datetime
    ) -> SentimentResult:
        if self._client is None:
            raise NotImplementedError("Claude scorer pending ANTHROPIC_API_KEY")
        # TODO: call self._client.messages.create(...) and parse JSON response
        raise NotImplementedError("Claude scorer pending ANTHROPIC_API_KEY")
