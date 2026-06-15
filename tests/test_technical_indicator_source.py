# tests/test_technical_indicator_source.py
"""TDD tests for TechnicalIndicatorSource wrapper."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from trader.core.events import BarEvent, Market, NormalizedSignal, Symbol
from trader.signals.indicators import MovingAverageCross, RsiReversion
from trader.signals.technical_indicator_source import TechnicalIndicatorSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

AAPL = Symbol("AAPL", Market.NASDAQ, "USD")
SAMSUNG = Symbol("005930", Market.KOSPI, "KRW")
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _bar(sym: Symbol, i: int, close: float) -> BarEvent:
    return BarEvent(sym, T0 + timedelta(days=i), close, close, close, close, 100)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTechnicalIndicatorSource:

    def test_supports_backtest_is_true(self):
        src = TechnicalIndicatorSource(name="test.ma", indicator=MovingAverageCross(5, 10))
        assert src.supports_backtest is True

    def test_warmup_returns_none_until_min_bars(self):
        """on_bar returns None for the first min_bars-1 calls."""
        ind = MovingAverageCross(fast=5, slow=10)
        src = TechnicalIndicatorSource(name="test.ma", indicator=ind)
        results = [src.on_bar(_bar(AAPL, i, float(i + 1))) for i in range(ind.min_bars - 1)]
        assert all(r is None for r in results), "Expected None during warmup"

    def test_emits_signal_after_warmup(self):
        """on_bar emits a NormalizedSignal once min_bars have been seen."""
        ind = MovingAverageCross(fast=5, slow=10)
        src = TechnicalIndicatorSource(name="test.ma", indicator=ind)
        sig = None
        for i in range(ind.min_bars + 3):
            sig = src.on_bar(_bar(AAPL, i, float(i + 1))) or sig
        assert sig is not None
        assert isinstance(sig, NormalizedSignal)

    def test_emitted_signal_uses_given_name(self):
        """NormalizedSignal.source must match the name passed at construction."""
        ind = MovingAverageCross(fast=5, slow=10)
        name = "technical.ma_10_30"
        src = TechnicalIndicatorSource(name=name, indicator=ind)
        sig = None
        for i in range(ind.min_bars + 3):
            sig = src.on_bar(_bar(AAPL, i, float(i + 1))) or sig
        assert sig is not None
        assert sig.source == name

    def test_per_symbol_isolation_opposite_sign(self):
        """Two symbols with opposite trends must produce signals of opposite sign.

        Interleave AAPL (rising) and Samsung (falling) bars through the SAME
        TechnicalIndicatorSource instance to confirm windows don't bleed.
        """
        ind = MovingAverageCross(fast=5, slow=10)
        src = TechnicalIndicatorSource(name="test.ma", indicator=ind)

        aapl_closes = [float(i + 1) for i in range(20)]      # 1, 2, ..., 20 (rising)
        samsung_closes = [float(20 - i) for i in range(20)]  # 20, 19, ..., 1 (falling)

        sig_aapl = sig_samsung = None
        for i in range(20):
            r = src.on_bar(_bar(AAPL, i * 2, aapl_closes[i]))
            if r is not None:
                sig_aapl = r
            r = src.on_bar(_bar(SAMSUNG, i * 2 + 1, samsung_closes[i]))
            if r is not None:
                sig_samsung = r

        assert sig_aapl is not None, "AAPL never produced a signal"
        assert sig_samsung is not None, "Samsung never produced a signal"
        assert sig_aapl.score > 0, f"AAPL (rising) should be positive, got {sig_aapl.score}"
        assert sig_samsung.score < 0, f"Samsung (falling) should be negative, got {sig_samsung.score}"

    def test_per_symbol_isolation_no_state_pollution(self):
        """Feeding only one symbol should not affect the other symbol's window."""
        ind = MovingAverageCross(fast=5, slow=10)
        src = TechnicalIndicatorSource(name="test.ma", indicator=ind)

        # Feed 15 bars for AAPL only
        for i in range(15):
            src.on_bar(_bar(AAPL, i, float(i + 1)))

        # Samsung should still be in warmup (no bars fed)
        result = src.on_bar(_bar(SAMSUNG, 0, 100.0))
        assert result is None, "Samsung should still be warming up with only 1 bar"

    def test_score_and_confidence_bounds(self):
        """All emitted signals must have score in [-1,1] and confidence in [0,1]."""
        ind = MovingAverageCross(fast=5, slow=10)
        src = TechnicalIndicatorSource(name="test.ma", indicator=ind)
        sigs = []
        for i in range(30):
            r = src.on_bar(_bar(AAPL, i, float(i + 1)))
            if r is not None:
                sigs.append(r)
        assert sigs, "No signals emitted"
        for s in sigs:
            assert -1.0 <= s.score <= 1.0
            assert 0.0 <= s.confidence <= 1.0

    def test_horizon_is_5d(self):
        """Wrapper always emits horizon='5d'."""
        ind = MovingAverageCross(fast=5, slow=10)
        src = TechnicalIndicatorSource(name="test.ma", indicator=ind)
        sig = None
        for i in range(ind.min_bars + 3):
            sig = src.on_bar(_bar(AAPL, i, float(i + 1))) or sig
        assert sig is not None
        assert sig.horizon == "5d"

    def test_rsi_source_per_symbol_isolation(self):
        """Same isolation test with RSI indicator."""
        ind = RsiReversion(period=14)
        src = TechnicalIndicatorSource(name="test.rsi", indicator=ind)

        aapl_closes = [100.0 - i * 3 for i in range(25)]   # falling → oversold → positive
        samsung_closes = [10.0 + i * 3 for i in range(25)] # rising → overbought → negative

        sig_aapl = sig_samsung = None
        for i in range(25):
            r = src.on_bar(_bar(AAPL, i * 2, aapl_closes[i]))
            if r is not None:
                sig_aapl = r
            r = src.on_bar(_bar(SAMSUNG, i * 2 + 1, samsung_closes[i]))
            if r is not None:
                sig_samsung = r

        assert sig_aapl is not None
        assert sig_samsung is not None
        assert sig_aapl.score > 0, f"AAPL oversold should be positive, got {sig_aapl.score}"
        assert sig_samsung.score < 0, f"Samsung overbought should be negative, got {sig_samsung.score}"

    def test_window_size_can_be_overridden(self):
        """window_size parameter controls maxlen of the deque."""
        ind = MovingAverageCross(fast=5, slow=10)
        src = TechnicalIndicatorSource(name="test.ma", indicator=ind, window_size=50)
        # Should still work; no error
        for i in range(60):
            src.on_bar(_bar(AAPL, i, float(i + 1)))
        # Verify window is capped at 50
        key = (AAPL.market.value, AAPL.ticker)
        assert src._windows[key].maxlen == 50
