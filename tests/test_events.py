# tests/test_events.py
import pytest
from datetime import datetime, timezone
from trader.core.events import Market, Side, Symbol, BarEvent, NormalizedSignal

def _ts(): return datetime(2026, 1, 2, tzinfo=timezone.utc)
_SYM = Symbol("AAPL", Market.NASDAQ, "USD")

def test_symbol_and_bar_are_immutable():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    bar = BarEvent(sym, _ts(), 10.0, 11.0, 9.5, 10.5, 1000)
    assert bar.is_closed and bar.timeframe == "1d"
    with pytest.raises(Exception):
        bar.close = 99  # frozen

def test_normalized_signal_rejects_out_of_range():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    with pytest.raises(ValueError):
        NormalizedSignal("technical", sym, _ts(), score=2.0, confidence=0.5, horizon="1d", features={})
    with pytest.raises(ValueError):
        NormalizedSignal("technical", sym, _ts(), score=0.1, confidence=1.5, horizon="1d", features={})

def test_bar_ts_must_be_timezone_aware():
    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    with pytest.raises(ValueError):
        BarEvent(sym, datetime(2026, 1, 2), 1, 1, 1, 1, 1)  # naive


# ---------------------------------------------------------------------------
# NormalizedSignal — boundary values that MUST be accepted (not rejected)
# ---------------------------------------------------------------------------

def test_normalized_signal_score_boundary_minus_one_accepted():
    """score exactly -1.0 is on the valid boundary and must not raise."""
    sig = NormalizedSignal("src", _SYM, _ts(), score=-1.0, confidence=0.5, horizon="1d")
    assert sig.score == -1.0


def test_normalized_signal_score_boundary_plus_one_accepted():
    """score exactly +1.0 is on the valid boundary and must not raise."""
    sig = NormalizedSignal("src", _SYM, _ts(), score=1.0, confidence=0.5, horizon="1d")
    assert sig.score == 1.0


def test_normalized_signal_confidence_boundary_zero_accepted():
    """confidence exactly 0.0 is on the valid boundary and must not raise."""
    sig = NormalizedSignal("src", _SYM, _ts(), score=0.0, confidence=0.0, horizon="1d")
    assert sig.confidence == 0.0


def test_normalized_signal_confidence_boundary_one_accepted():
    """confidence exactly 1.0 is on the valid boundary and must not raise."""
    sig = NormalizedSignal("src", _SYM, _ts(), score=0.0, confidence=1.0, horizon="1d")
    assert sig.confidence == 1.0


def test_normalized_signal_score_just_outside_raises():
    """score just outside [-1, 1] must raise ValueError (both sides)."""
    with pytest.raises(ValueError):
        NormalizedSignal("src", _SYM, _ts(), score=-1.0001, confidence=0.5, horizon="1d")
    with pytest.raises(ValueError):
        NormalizedSignal("src", _SYM, _ts(), score=1.0001, confidence=0.5, horizon="1d")


def test_normalized_signal_confidence_just_outside_raises():
    """confidence just outside [0, 1] must raise ValueError (both sides)."""
    with pytest.raises(ValueError):
        NormalizedSignal("src", _SYM, _ts(), score=0.0, confidence=-0.0001, horizon="1d")
    with pytest.raises(ValueError):
        NormalizedSignal("src", _SYM, _ts(), score=0.0, confidence=1.0001, horizon="1d")
