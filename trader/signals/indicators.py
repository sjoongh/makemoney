# trader/signals/indicators.py
"""Pure, stateless technical indicator implementations.

Each indicator:
- Is a frozen dataclass (no mutable state).
- Accepts a Sequence[BarEvent] window passed in from outside.
- Returns IndicatorResult | None (None when fewer than min_bars supplied).
- Has regime-aware confidence bounded ~[0.1, 0.9].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from trader.core.events import BarEvent


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndicatorResult:
    score: float        # [-1, 1]
    confidence: float   # [0, 1]
    reason: str | None = None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class TechnicalIndicator(Protocol):
    @property
    def min_bars(self) -> int: ...
    def evaluate(self, bars: Sequence[BarEvent]) -> IndicatorResult | None: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _sma(values: list[float], n: int) -> float:
    return sum(values[-n:]) / n


def _ema(values: list[float], n: int) -> float:
    """Exponential moving average of the last elements of *values* using span n."""
    k = 2.0 / (n + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1.0 - k)
    return e


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5


# ---------------------------------------------------------------------------
# 1. MovingAverageCross
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MovingAverageCross:
    """Score = clamp((ma_fast - ma_slow) / ma_slow * k, -1, 1).

    Confidence increases with |spread| (trend strength), low when choppy.
    """
    fast: int = 10
    slow: int = 30
    k: float = 20.0  # scaling factor so typical small % moves map to ±1

    @property
    def min_bars(self) -> int:
        return self.slow

    def evaluate(self, bars: Sequence[BarEvent]) -> IndicatorResult | None:
        if len(bars) < self.min_bars:
            return None
        closes = [b.close for b in bars]
        ma_fast = _sma(closes, self.fast)
        ma_slow = _sma(closes, self.slow)
        if ma_slow == 0:
            return None
        spread_pct = (ma_fast - ma_slow) / ma_slow
        score = _clamp(spread_pct * self.k, -1.0, 1.0)
        # Confidence: higher when |spread| is large (clear trend), lower when tiny (chop).
        # Map |spread_pct| through sigmoid-like stretch; cap at 0.9.
        abs_spread = abs(spread_pct)
        confidence = _clamp(0.1 + 0.8 * (abs_spread * self.k / (1.0 + abs_spread * self.k)), 0.1, 0.9)
        return IndicatorResult(score=score, confidence=confidence,
                               reason=f"ma_fast={ma_fast:.4f} ma_slow={ma_slow:.4f}")


# ---------------------------------------------------------------------------
# 2. RsiReversion
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RsiReversion:
    """Score positive when RSI < oversold (buy dip), negative when > overbought.

    Confidence low near 50, high at extremes.
    """
    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0

    @property
    def min_bars(self) -> int:
        return self.period + 1

    def _rsi(self, closes: list[float]) -> float:
        import numpy as np  # available — used by technical.py already
        if len(closes) < self.period + 1:
            return 50.0
        d = [closes[i] - closes[i - 1] for i in range(len(closes) - self.period, len(closes))]
        ups = sum(x for x in d if x > 0) / self.period
        dns = sum(-x for x in d if x < 0) / self.period
        if dns == 0:
            return 100.0
        rs = ups / dns
        return 100.0 - 100.0 / (1.0 + rs)

    def evaluate(self, bars: Sequence[BarEvent]) -> IndicatorResult | None:
        if len(bars) < self.min_bars:
            return None
        closes = [b.close for b in bars]
        rsi = self._rsi(closes)
        mid = (self.oversold + self.overbought) / 2.0  # typically 50
        half_range = (self.overbought - self.oversold) / 2.0  # typically 20

        # Score: positive (buy) when oversold, negative (sell) when overbought, ~0 near mid.
        # Normalise distance from midpoint to [-1, 1]; flip sign so low RSI → positive score.
        normalised = (mid - rsi) / (mid if mid else 50.0)
        score = _clamp(normalised, -1.0, 1.0)

        # Confidence: distance from mid determines regime clarity.
        distance_from_mid = abs(rsi - mid)
        confidence = _clamp(0.1 + 0.8 * (distance_from_mid / (mid if mid else 50.0)), 0.1, 0.9)
        return IndicatorResult(score=score, confidence=confidence,
                               reason=f"rsi={rsi:.2f}")


# ---------------------------------------------------------------------------
# 3. MacdTrend
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MacdTrend:
    """MACD line = ema_fast - ema_slow; signal = ema(MACD, signal_period).

    Score from histogram (MACD - signal). Confidence higher when histogram
    agrees with MACD line sign; lower near zero-cross.
    """
    fast: int = 12
    slow: int = 26
    signal: int = 9

    @property
    def min_bars(self) -> int:
        return self.slow + self.signal

    def evaluate(self, bars: Sequence[BarEvent]) -> IndicatorResult | None:
        if len(bars) < self.min_bars:
            return None
        closes = [b.close for b in bars]
        # Build a MACD time-series over the tail we have.
        macd_series: list[float] = []
        # Need at least `slow` bars to compute MACD; build for signal window.
        needed = self.slow + self.signal - 1
        if len(closes) < needed:
            return None
        tail = closes[-needed:]
        for i in range(self.signal):
            window = tail[: self.slow + i]
            macd_series.append(_ema(window, self.fast) - _ema(window, self.slow))

        macd_line = macd_series[-1]
        signal_line = _ema(macd_series, self.signal)
        histogram = macd_line - signal_line

        # Scale by a representative price level to get a unit-less score.
        price_ref = closes[-1] or 1.0
        score = _clamp(histogram / price_ref * 100.0, -1.0, 1.0)

        # Confidence: high when histogram and MACD agree in sign (momentum aligned).
        same_sign = (histogram * macd_line) > 0
        abs_hist_norm = abs(histogram) / (price_ref * 0.01 + abs(histogram))
        if same_sign:
            confidence = _clamp(0.5 + 0.4 * abs_hist_norm, 0.1, 0.9)
        else:
            confidence = _clamp(0.1 + 0.3 * abs_hist_norm, 0.1, 0.9)
        return IndicatorResult(score=score, confidence=confidence,
                               reason=f"hist={histogram:.4f} macd={macd_line:.4f}")


# ---------------------------------------------------------------------------
# 4. BollingerReversion
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BollingerReversion:
    """Mean-reversion: score positive near/below lower band, negative near/above upper.

    Confidence higher outside bands, lower inside; reduced when band width is tiny.
    """
    period: int = 20
    stdevs: float = 2.0

    @property
    def min_bars(self) -> int:
        return self.period

    def evaluate(self, bars: Sequence[BarEvent]) -> IndicatorResult | None:
        if len(bars) < self.min_bars:
            return None
        closes = [b.close for b in bars]
        window = closes[-self.period:]
        mean = sum(window) / len(window)
        std = _stdev(window)
        price = closes[-1]

        if std == 0 or mean == 0:
            return IndicatorResult(score=0.0, confidence=0.1, reason="zero_std")

        upper = mean + self.stdevs * std
        lower = mean - self.stdevs * std
        band_width_pct = (upper - lower) / mean  # 0 when perfectly flat

        # Position within bands: 0=mean, +1=upper, -1=lower; clipped.
        # Score is inverted: below lower → positive (expect reversion up).
        bb_z = (price - mean) / (self.stdevs * std)  # +1 at upper band, -1 at lower
        score = _clamp(-bb_z, -1.0, 1.0)  # flip: low price → positive score

        # Confidence: high when outside bands; low inside; reduced when tiny band width.
        abs_z = abs(bb_z)
        base_conf = _clamp(0.1 + 0.5 * (abs_z - 1.0), 0.1, 0.9) if abs_z >= 1.0 else _clamp(0.1 + 0.3 * abs_z, 0.1, 0.4)
        # Reduce confidence when band is very narrow (< 1% of price).
        width_penalty = _clamp(band_width_pct / 0.01, 0.2, 1.0)
        confidence = _clamp(base_conf * width_penalty, 0.1, 0.9)
        return IndicatorResult(score=score, confidence=confidence,
                               reason=f"bb_z={bb_z:.3f} bw={band_width_pct:.4f}")
