"""NewsSignalSource — live-only, look-ahead-safe, cached, time-decayed.

Aggregation formula
-------------------
For each relevant item i (published_at <= bar.ts):
  age_days_i  = max(0, (bar.ts - item.published_at).total_seconds() / 86400)
  w_i         = 0.5 ** (age_days_i / halflife_days)        # exponential half-life
  ew_i        = w_i * result_i.confidence                  # effective weight

combined_score = clamp(sum(score_i * ew_i) / sum(ew_i), -1, 1)   if sum(ew_i) > 0
combined_conf  = min(1.0, max(w_i * result_i.confidence for all i))
                # = the largest single decayed-confidence across all items,
                #   bounded to [0, 1].  This is a simple, monotone measure:
                #   the most-credible recent item determines our certainty ceiling,
                #   while stale items naturally shrink this ceiling via w_i.

Emit None when there are zero relevant items in the window.
Otherwise always emit (signal persists/fades across bars via decay).
Mark all current item ids as seen for dedup tracking (reserved for
future sparse-emission tuning; current policy always emits when items > 0).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from trader.core.events import BarEvent, NormalizedSignal
from trader.signals.news.cache import SentimentCache
from trader.signals.news.providers import NewsProvider
from trader.signals.news.sentiment import SentimentScorer


def _clamp(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class NewsSignalSource:
    """Aggregates time-decayed LLM sentiment into a single NormalizedSignal.

    This source is live-only: it calls external news providers and LLM scorers
    that are inherently non-deterministic and I/O-bound.  It must NEVER be
    wired into the backtest engine.

    supports_backtest = False declares this contract explicitly so that any
    engine wiring code can check and reject it at construction time.
    """

    name: str = "news_llm"
    supports_backtest: bool = False

    def __init__(
        self,
        provider: NewsProvider,
        scorer: SentimentScorer,
        cache: Optional[SentimentCache] = None,
        *,
        lookback: timedelta = timedelta(days=7),
        halflife_days: float = 3.0,
        source_name: str = "news_llm",
    ) -> None:
        self.provider = provider
        self.scorer = scorer
        self.cache: SentimentCache = cache if cache is not None else SentimentCache()
        self.lookback = lookback
        self.halflife_days = halflife_days
        self.name = source_name
        self._seen_ids: set[str] = set()

    def on_bar(self, bar: BarEvent) -> Optional[NormalizedSignal]:
        """Process one closed bar and return an aggregated sentiment signal or None.

        Steps:
        1. Fetch items from provider (provider contract: published_at <= bar.ts).
        2. Defensive re-filter: drop anything with published_at > bar.ts.
        3. Score ALL items in the window via cache (each item scored exactly once).
        4. Time-decay weighted aggregation → combined_score, combined_conf.
        5. Return None if no items; otherwise emit NormalizedSignal and update seen set.
        """
        # Step 1: fetch
        raw_items = self.provider.fetch_as_of(
            bar.symbol.ticker, bar.ts, self.lookback
        )

        # Step 2: defensive look-ahead re-filter
        items = [it for it in raw_items if it.published_at <= bar.ts]

        if not items:
            return None

        # Step 3: score all (cache ensures each item.id scored only once)
        scored = [
            (item, self.cache.get_or_score(
                item, self.scorer, symbol=bar.symbol.ticker, as_of=bar.ts
            ))
            for item in items
        ]

        # Step 4: time-decay weighted aggregation
        weighted_scores: list[float] = []
        effective_weights: list[float] = []
        decayed_confs: list[float] = []

        for item, result in scored:
            age_days = max(
                0.0,
                (bar.ts - item.published_at).total_seconds() / 86400.0,
            )
            w = 0.5 ** (age_days / self.halflife_days)
            ew = w * result.confidence
            weighted_scores.append(result.score * ew)
            effective_weights.append(ew)
            decayed_confs.append(w * result.confidence)

        total_ew = sum(effective_weights)
        if total_ew > 0.0:
            combined_score = _clamp(sum(weighted_scores) / total_ew)
        else:
            combined_score = 0.0

        # Confidence: max decayed confidence across all items, clamped [0, 1].
        # Rationale: the single most credible & recent item sets the confidence
        # ceiling; stale items shrink their own contribution via w < 1.
        combined_conf = _clamp(max(decayed_confs), 0.0, 1.0)

        # Step 5: mark seen, emit signal
        for item in items:
            self._seen_ids.add(item.id)

        return NormalizedSignal(
            source=self.name,
            symbol=bar.symbol,
            ts=bar.ts,
            score=combined_score,
            confidence=combined_conf,
            horizon="5d",
            features={
                "n_items": float(len(items)),
                "raw_combined": combined_score,
            },
        )
