# tests/test_disclaimers.py
"""Tests for survivorship-bias disclaimers (P0 foundation).

Verifies that:
  1. SURVIVORSHIP_WARNING is a non-empty string with required key phrases.
  2. format_momentum_report output CONTAINS the survivorship warning text.
  3. format_report (evaluate) output CONTAINS the survivorship warning text.
  4. equal_weight_buyhold computes correctly on a known 2-symbol series.
  5. evaluate() result dict includes 'equal_weight_buyhold' key.
  6. universe() emits a survivorship-bias log warning when called.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from trader.backtest.evaluate import (
    equal_weight_buyhold,
    evaluate,
    format_report,
    _INITIAL_KRW,
)
from trader.core.events import BarEvent, Market, Symbol
from trader.research.disclaimers import SURVIVORSHIP_WARNING
from trader.research.momentum import cross_sectional_momentum, format_momentum_report

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYM_A = Symbol("AAPL", Market.NASDAQ, "USD")
SYM_B = Symbol("005930", Market.KOSPI, "KRW")
T0 = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _bars_for(sym: Symbol, closes: list[float]) -> list[BarEvent]:
    return [
        BarEvent(sym, T0 + timedelta(days=i), c, c, c, c, 1000)
        for i, c in enumerate(closes)
    ]


def _make_momentum_bars(n: int = 350) -> dict[str, list[BarEvent]]:
    """3-symbol synthetic universe suitable for cross_sectional_momentum."""
    from datetime import date

    def _make(ticker: str, closes: list[float]) -> list[BarEvent]:
        sym = Symbol(ticker, Market.NASDAQ, "USD")
        d = datetime(2018, 1, 2, tzinfo=timezone.utc)
        bars = []
        for i, c in enumerate(closes):
            bars.append(BarEvent(sym, d + timedelta(days=i), c, c, c, c, 1_000_000))
        return bars

    strong = _make("STRONG", [100.0 + i * (100.0 / n) for i in range(n)])
    flat   = _make("FLAT",   [100.0] * n)
    weak   = _make("WEAK",   [100.0 - i * (50.0 / n) for i in range(n)])
    return {"STRONG": strong, "FLAT": flat, "WEAK": weak}


# ---------------------------------------------------------------------------
# Part 1: SURVIVORSHIP_WARNING constant
# ---------------------------------------------------------------------------

def test_survivorship_warning_is_non_empty_string():
    assert isinstance(SURVIVORSHIP_WARNING, str)
    assert len(SURVIVORSHIP_WARNING) > 100


def test_survivorship_warning_contains_key_phrases():
    w = SURVIVORSHIP_WARNING
    assert "SURVIVORSHIP" in w.upper()
    assert "CURRENT" in w.upper() or "current" in w
    assert "delisted" in w.lower() or "DELISTED" in w
    assert "point-in-time" in w.lower() or "POINT-IN-TIME" in w


# ---------------------------------------------------------------------------
# Part 2: format_momentum_report contains survivorship warning
# ---------------------------------------------------------------------------

def test_format_momentum_report_contains_survivorship_warning():
    bars = _make_momentum_bars()
    result = cross_sectional_momentum(bars, init_capital=1_000_000)
    report = format_momentum_report(result)

    # The canonical warning block must appear verbatim
    assert "SURVIVORSHIP-BIASED EXPLORATORY ONLY" in report, (
        "format_momentum_report is missing the canonical survivorship warning header"
    )
    assert "CURRENT" in report.upper(), (
        "format_momentum_report missing 'current constituents' language"
    )
    assert "point-in-time" in report.lower() or "NOT evidence" in report, (
        "format_momentum_report missing point-in-time or credibility caveat"
    )


def test_format_momentum_report_contains_research_diagnostic_caveat():
    """The existing RESEARCH/DIAGNOSTIC caveat at the bottom must also be present."""
    bars = _make_momentum_bars()
    result = cross_sectional_momentum(bars, init_capital=1_000_000)
    report = format_momentum_report(result)

    assert "RESEARCH/DIAGNOSTIC" in report
    assert "survivorship bias" in report.lower()
    # The report must state that results are not credible evidence of edge
    # (phrased either in the warning block or in the bottom caveat)
    assert "NOT evidence" in report or "credible evidence" in report.lower()


# ---------------------------------------------------------------------------
# Part 3: format_report (evaluate) contains survivorship warning
# ---------------------------------------------------------------------------

RISES = [100.0 + i * 0.5 for i in range(60)]
FLAT  = [60000.0] * 60


def test_format_report_contains_survivorship_warning():
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10, 0.35))
    report = format_report(result)

    assert "SURVIVORSHIP-BIASED EXPLORATORY ONLY" in report, (
        "format_report (evaluate) is missing the canonical survivorship warning header"
    )
    assert "CURRENT" in report.upper()
    assert "delisted" in report.lower()


def test_format_report_still_contains_diagnostic_disclaimer():
    """The engine-validation DIAGNOSTIC ONLY block must remain alongside the warning."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10,))
    report = format_report(result)

    assert "DIAGNOSTIC ONLY" in report
    assert "statistically insignificant" in report


def test_format_report_contains_benchmark_section():
    """format_report must show an explicit benchmark section with labelled entries."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10,))
    report = format_report(result)

    assert "BENCHMARKS" in report.upper()
    assert "Buy & Hold" in report or "buy_and_hold" in report.lower()
    assert "Equal-Weight Buy & Hold" in report or "equal_weight" in report.lower()


# ---------------------------------------------------------------------------
# Part 4: equal_weight_buyhold — hand-verified correctness
# ---------------------------------------------------------------------------

def test_equal_weight_buyhold_two_symbol_known_return():
    """Hand-verified: SYM_A 100→110 (+10%), SYM_B 60000→60000 (0%) → avg +5%.

    equal_weight_buyhold must return total_return ≈ +5%.
    """
    bars_a = _bars_for(SYM_A, [100.0, 110.0])
    bars_b = _bars_for(SYM_B, [60000.0, 60000.0])
    bars_by_symbol = {
        "AAPL":   bars_a,
        "005930": bars_b,
    }

    curve, metrics = equal_weight_buyhold(bars_by_symbol)

    assert metrics["n_symbols"] == 2
    assert metrics["n_dates"] == 2
    assert abs(metrics["total_return"] - 0.05) < 1e-6, (
        f"Expected total_return ≈ +5%, got {metrics['total_return']:+.6f}"
    )


def test_equal_weight_buyhold_flat_is_zero():
    """All-flat universe → total_return == 0.0."""
    bars_a = _bars_for(SYM_A, [100.0, 100.0, 100.0])
    bars_b = _bars_for(SYM_B, [50000.0, 50000.0, 50000.0])
    bars_by_symbol = {"AAPL": bars_a, "005930": bars_b}

    curve, metrics = equal_weight_buyhold(bars_by_symbol)

    assert abs(metrics["total_return"]) < 1e-9


def test_equal_weight_buyhold_single_symbol_matches_individual_return():
    """Single symbol 100→150 → +50% total return."""
    bars_a = _bars_for(SYM_A, [100.0, 125.0, 150.0])
    curve, metrics = equal_weight_buyhold({"AAPL": bars_a})

    assert metrics["n_symbols"] == 1
    assert abs(metrics["total_return"] - 0.50) < 1e-6, (
        f"Expected +50%, got {metrics['total_return']:+.6f}"
    )


def test_equal_weight_buyhold_curve_length_matches_dates():
    """Curve must have one entry per unique date across all symbols."""
    bars_a = _bars_for(SYM_A, [100.0, 110.0, 120.0])
    bars_b = _bars_for(SYM_B, [60000.0, 60000.0, 60000.0])
    bars_by_symbol = {"AAPL": bars_a, "005930": bars_b}

    curve, metrics = equal_weight_buyhold(bars_by_symbol)

    assert len(curve) == 3
    assert metrics["n_dates"] == 3


def test_equal_weight_buyhold_empty_input():
    """Empty input must return empty curve and zero metrics."""
    curve, metrics = equal_weight_buyhold({})

    assert curve == []
    assert metrics["total_return"] == 0.0
    assert metrics["n_symbols"] == 0


def test_equal_weight_buyhold_initial_equity_is_initial_krw():
    """At t=0 (all bars start at their first price) equity must equal _INITIAL_KRW."""
    bars_a = _bars_for(SYM_A, [100.0, 110.0])
    bars_b = _bars_for(SYM_B, [60000.0, 63000.0])
    bars_by_symbol = {"AAPL": bars_a, "005930": bars_b}

    curve, _ = equal_weight_buyhold(bars_by_symbol)

    # First point: both symbols at their first price → curve[0] == _INITIAL_KRW
    assert abs(curve[0] - _INITIAL_KRW) < 1.0, (
        f"Expected curve[0] ≈ {_INITIAL_KRW:,.0f}, got {curve[0]:,.0f}"
    )


# ---------------------------------------------------------------------------
# Part 5: evaluate() result includes equal_weight_buyhold key
# ---------------------------------------------------------------------------

def test_evaluate_result_contains_equal_weight_buyhold():
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10,))

    assert "equal_weight_buyhold" in result, (
        "evaluate() result dict must contain 'equal_weight_buyhold' key"
    )
    ewbh = result["equal_weight_buyhold"]
    assert "total_return" in ewbh
    assert "n_symbols" in ewbh
    assert "n_dates" in ewbh
    assert ewbh["n_symbols"] > 0


# ---------------------------------------------------------------------------
# Part 6: universe() emits a survivorship-bias log warning
# ---------------------------------------------------------------------------

def test_universe_emits_survivorship_warning(caplog, monkeypatch):
    """universe() must emit a WARNING-level log containing survivorship language."""
    # Monkeypatch load_sp500 to avoid real network calls
    import trader.data.universe as _u
    monkeypatch.setattr(_u, "load_sp500", lambda: ["AAPL", "MSFT"])

    with caplog.at_level(logging.WARNING, logger="trader.data.universe"):
        _u.universe(us_limit=2, kr=False)

    warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("SURVIVORSHIP" in m.upper() or "survivorship" in m.lower()
               for m in warning_msgs), (
        f"universe() must log a survivorship-bias warning. Got: {warning_msgs}"
    )
