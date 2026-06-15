# tests/test_indicators.py
"""TDD tests for pure technical indicators in trader/signals/indicators.py."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from trader.core.events import BarEvent, Market, Symbol
from trader.signals.indicators import (
    BollingerReversion,
    IndicatorResult,
    MacdTrend,
    MovingAverageCross,
    RsiReversion,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _bar(i: int, close: float) -> BarEvent:
    return BarEvent(SYM, T0 + timedelta(days=i), close, close, close, close, 100)


def _bars(closes: list[float]) -> list[BarEvent]:
    return [_bar(i, c) for i, c in enumerate(closes)]


# ---------------------------------------------------------------------------
# MovingAverageCross
# ---------------------------------------------------------------------------

class TestMovingAverageCross:
    def test_returns_none_below_min_bars(self):
        ind = MovingAverageCross(fast=5, slow=10)
        bars = _bars([1.0] * 9)  # one short of min_bars=10
        assert ind.evaluate(bars) is None

    def test_uptrend_yields_positive_score(self):
        ind = MovingAverageCross(fast=5, slow=10)
        # Clear uptrend: fast MA > slow MA
        closes = list(range(1, 21))  # 1..20 strongly rising
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score > 0, f"expected positive score, got {result.score}"

    def test_downtrend_yields_negative_score(self):
        ind = MovingAverageCross(fast=5, slow=10)
        # Clear downtrend: fast MA < slow MA
        closes = list(range(20, 0, -1))  # 20..1 strongly falling
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score < 0, f"expected negative score, got {result.score}"

    def test_confidence_in_range(self):
        ind = MovingAverageCross(fast=5, slow=10)
        closes = list(range(1, 21))
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert 0.0 < result.confidence < 1.0, f"confidence out of range: {result.confidence}"

    def test_flat_market_low_confidence(self):
        ind = MovingAverageCross(fast=5, slow=10)
        closes = [100.0] * 20  # completely flat — no spread
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        # Near-zero spread → low confidence
        assert result.confidence < 0.3, f"expected low confidence for flat market, got {result.confidence}"

    def test_strong_trend_higher_confidence_than_flat(self):
        ind = MovingAverageCross(fast=5, slow=10)
        flat_bars = _bars([100.0] * 20)
        trend_bars = _bars(list(range(1, 21)))
        flat_result = ind.evaluate(flat_bars)
        trend_result = ind.evaluate(trend_bars)
        assert flat_result is not None and trend_result is not None
        assert trend_result.confidence > flat_result.confidence


# ---------------------------------------------------------------------------
# RsiReversion
# ---------------------------------------------------------------------------

class TestRsiReversion:
    def test_returns_none_below_min_bars(self):
        ind = RsiReversion(period=14)
        bars = _bars([1.0] * 14)  # need period+1=15
        assert ind.evaluate(bars) is None

    def test_oversold_yields_positive_score(self):
        ind = RsiReversion(period=14, oversold=30, overbought=70)
        # Price falling hard → RSI very low → positive score (buy the dip)
        closes = [100.0 - i * 3 for i in range(20)]  # 100, 97, 94, ... falling
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score > 0, f"expected positive score for oversold, got {result.score}"

    def test_overbought_yields_negative_score(self):
        ind = RsiReversion(period=14, oversold=30, overbought=70)
        # Price rising hard → RSI very high → negative score (sell the rip)
        closes = [100.0 + i * 3 for i in range(20)]
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score < 0, f"expected negative score for overbought, got {result.score}"

    def test_confidence_in_range(self):
        ind = RsiReversion(period=14)
        closes = [100.0 - i * 3 for i in range(20)]
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert 0.0 < result.confidence < 1.0

    def test_extreme_rsi_higher_confidence_than_neutral(self):
        ind = RsiReversion(period=14)
        # Neutral: alternating up/down → RSI ~50
        neutral_closes = [100.0 + (1 if i % 2 == 0 else -1) for i in range(20)]
        # Extreme: all falling → RSI very low
        extreme_closes = [100.0 - i * 3 for i in range(20)]
        neutral_result = ind.evaluate(_bars(neutral_closes))
        extreme_result = ind.evaluate(_bars(extreme_closes))
        assert neutral_result is not None and extreme_result is not None
        assert extreme_result.confidence > neutral_result.confidence


# ---------------------------------------------------------------------------
# MacdTrend
# ---------------------------------------------------------------------------

class TestMacdTrend:
    def test_returns_none_below_min_bars(self):
        ind = MacdTrend(fast=12, slow=26, signal=9)
        bars = _bars([1.0] * (26 + 9 - 1))  # one short
        assert ind.evaluate(bars) is None

    def test_uptrend_yields_positive_score(self):
        ind = MacdTrend(fast=12, slow=26, signal=9)
        # Strong persistent uptrend: fast EMA > slow EMA → positive histogram
        closes = [10.0 + i * 0.5 for i in range(50)]
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score > 0, f"expected positive score for uptrend, got {result.score}"

    def test_downtrend_yields_negative_score(self):
        ind = MacdTrend(fast=12, slow=26, signal=9)
        closes = [50.0 - i * 0.5 for i in range(50)]
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score < 0, f"expected negative score for downtrend, got {result.score}"

    def test_confidence_in_range(self):
        ind = MacdTrend(fast=12, slow=26, signal=9)
        closes = [10.0 + i * 0.5 for i in range(50)]
        bars = _bars(closes)
        result = ind.evaluate(bars)
        assert result is not None
        assert 0.0 < result.confidence < 1.0

    def test_min_bars_is_slow_plus_signal(self):
        ind = MacdTrend(fast=12, slow=26, signal=9)
        assert ind.min_bars == 35


# ---------------------------------------------------------------------------
# BollingerReversion
# ---------------------------------------------------------------------------

class TestBollingerReversion:
    def test_returns_none_below_min_bars(self):
        ind = BollingerReversion(period=20)
        bars = _bars([1.0] * 19)
        assert ind.evaluate(bars) is None

    def test_price_below_lower_band_positive_score(self):
        ind = BollingerReversion(period=20, stdevs=2.0)
        # Stable prices then a sharp drop → price far below lower band
        base = [100.0] * 19
        spike_down = base + [80.0]  # ~10 std below
        bars = _bars(spike_down)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score > 0, f"expected positive score below lower band, got {result.score}"

    def test_price_above_upper_band_negative_score(self):
        ind = BollingerReversion(period=20, stdevs=2.0)
        base = [100.0] * 19
        spike_up = base + [120.0]  # far above upper band
        bars = _bars(spike_up)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score < 0, f"expected negative score above upper band, got {result.score}"

    def test_confidence_in_range(self):
        ind = BollingerReversion(period=20, stdevs=2.0)
        base = [100.0] * 19 + [80.0]
        bars = _bars(base)
        result = ind.evaluate(bars)
        assert result is not None
        assert 0.0 < result.confidence < 1.0

    def test_outside_band_higher_confidence_than_inside(self):
        ind = BollingerReversion(period=20, stdevs=2.0)
        # Inside band: price at mean
        inside = [100.0] * 20
        # Outside band: sharp spike
        outside = [100.0] * 19 + [80.0]
        inside_result = ind.evaluate(_bars(inside))
        outside_result = ind.evaluate(_bars(outside))
        # outside (deviation) should be higher confidence than inside (at mean)
        assert outside_result is not None
        assert inside_result is not None
        assert outside_result.confidence > inside_result.confidence

    def test_flat_prices_returns_zero_score_low_confidence(self):
        """Perfectly flat prices → zero std → score 0, low confidence."""
        ind = BollingerReversion(period=20, stdevs=2.0)
        bars = _bars([100.0] * 20)
        result = ind.evaluate(bars)
        assert result is not None
        assert result.score == 0.0
        assert result.confidence <= 0.1
