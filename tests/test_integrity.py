# tests/test_integrity.py
"""Tests for data-integrity guards (time / FX / tick)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from trader.core.events import BarEvent, Market, Symbol
from trader.data.integrity import (
    check_duplicate_dates,
    check_stale,
    flag_price_jumps,
    validate_fx_rate,
)

_SYM = Symbol("AAPL", Market.NASDAQ, "USD")
_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _bar(day_offset: int, close: float) -> BarEvent:
    ts = _T0 + timedelta(days=day_offset)
    return BarEvent(_SYM, ts, close, close + 1, close - 1, close, 1000)


# --- stale ---

def test_stale_flagged_when_old():
    bars = [_bar(0, 100)]
    issue = check_stale(bars, as_of=date(2026, 1, 20), max_age_days=5)
    assert issue is not None and issue.code == "STALE" and issue.severity == "FAIL"


def test_not_stale_when_recent():
    bars = [_bar(0, 100), _bar(3, 101)]
    assert check_stale(bars, as_of=date(2026, 1, 5), max_age_days=5) is None


def test_empty_series_is_fail():
    assert check_stale([], as_of=date(2026, 1, 5)).code == "NO_BARS"


# --- duplicate dates ---

def test_duplicate_dates_detected():
    bars = [_bar(0, 100), _bar(1, 101), _bar(1, 102), _bar(2, 103)]
    dups = check_duplicate_dates(bars)
    assert dups == [(_T0 + timedelta(days=1)).date()]


def test_no_duplicates():
    assert check_duplicate_dates([_bar(0, 100), _bar(1, 101)]) == []


# --- FX ---

def test_fx_valid():
    assert validate_fx_rate(1300.0) is None


def test_fx_nonpositive_fails():
    assert validate_fx_rate(0).code == "FX_NONPOSITIVE"
    assert validate_fx_rate(-5).code == "FX_NONPOSITIVE"


def test_fx_out_of_band_fails():
    assert validate_fx_rate(1e9).code == "FX_OUT_OF_BAND"


def test_fx_non_numeric_fails():
    assert validate_fx_rate("oops").code == "FX_BAD"


def test_fx_nan_fails():
    assert validate_fx_rate(float("nan")).code == "FX_NAN"


# --- price jumps ---

def test_price_jump_flagged():
    # 100 -> 200 is a +100% move (> 50% threshold)
    bars = [_bar(0, 100), _bar(1, 200), _bar(2, 205)]
    jumps = flag_price_jumps(bars, threshold=0.5)
    assert len(jumps) == 1
    assert jumps[0][0] == (_T0 + timedelta(days=1)).date()
    assert jumps[0][1] > 0.9


def test_no_jump_under_threshold():
    bars = [_bar(0, 100), _bar(1, 110), _bar(2, 120)]  # +10% moves
    assert flag_price_jumps(bars, threshold=0.5) == []


def test_downward_jump_flagged():
    bars = [_bar(0, 100), _bar(1, 40)]  # -60%
    jumps = flag_price_jumps(bars, threshold=0.5)
    assert len(jumps) == 1 and jumps[0][1] < -0.5
