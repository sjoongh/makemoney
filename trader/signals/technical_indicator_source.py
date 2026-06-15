# trader/signals/technical_indicator_source.py
"""TechnicalIndicatorSource — per-symbol rolling window wrapper for TechnicalIndicator.

Usage::

    from trader.signals.technical_indicator_source import TechnicalIndicatorSource
    from trader.signals.indicators import MovingAverageCross

    src = TechnicalIndicatorSource(name="technical.ma_10_30",
                                   indicator=MovingAverageCross(10, 30))
    signal = src.on_bar(bar)   # NormalizedSignal | None
"""
from __future__ import annotations

from collections import deque

from trader.core.events import BarEvent, NormalizedSignal
from trader.signals.indicators import TechnicalIndicator


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class TechnicalIndicatorSource:
    """Wraps any TechnicalIndicator with per-symbol rolling window management.

    Instantiate multiple times with distinct *name* values; fuse by weight in
    FusionEngine via source_weight={name: weight}.
    """

    supports_backtest: bool = True

    def __init__(
        self,
        *,
        name: str,
        indicator: TechnicalIndicator,
        window_size: int | None = None,
    ) -> None:
        self.name = name
        self.indicator = indicator
        self.window_size = window_size or indicator.min_bars
        # key: (market.value, ticker) → deque of BarEvents
        self._windows: dict[tuple[str, str], deque[BarEvent]] = {}

    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
        key = (bar.symbol.market.value, bar.symbol.ticker)
        max_len = max(self.window_size, self.indicator.min_bars)
        if key not in self._windows:
            self._windows[key] = deque(maxlen=max_len)
        w = self._windows[key]
        w.append(bar)
        if len(w) < self.indicator.min_bars:
            return None
        result = self.indicator.evaluate(tuple(w))
        if result is None:
            return None
        features: dict[str, float] = {}
        if result.reason:
            features["reason_set"] = 1.0
        return NormalizedSignal(
            source=self.name,
            symbol=bar.symbol,
            ts=bar.ts,
            score=_clamp(result.score, -1.0, 1.0),
            confidence=_clamp(result.confidence, 0.0, 1.0),
            horizon="5d",
            features=features,
        )
