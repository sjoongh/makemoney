# tests/test_evaluate.py
"""Unit tests for trader.backtest.evaluate — engine-validation harness.

Uses a deterministic synthetic InMemoryDailyFeed.  We assert structural
correctness (field types, invariants, hand-computable buy-and-hold), NOT
profitability — see the DIAGNOSTIC ONLY disclaimer in format_report.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from trader.backtest.evaluate import (
    StrategyStats,
    buy_and_hold_return,
    evaluate,
    format_report,
    run_strategy,
)
from trader.core.events import BarEvent, Market, Symbol
from trader.data.historical_feed import InMemoryDailyFeed
from trader.signals.indicators import MovingAverageCross
from trader.signals.technical_indicator_source import TechnicalIndicatorSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager

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


def _make_feed(
    closes_a: list[float], closes_b: list[float]
) -> tuple[InMemoryDailyFeed, dict[str, list[BarEvent]]]:
    """Create a two-symbol feed and return the bars dict keyed by ticker."""
    bars_a = _bars_for(SYM_A, closes_a)
    bars_b = _bars_for(SYM_B, closes_b)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))
    feed = InMemoryDailyFeed(all_bars)
    return feed, {"AAPL": bars_a, "005930": bars_b}


# 60-bar rising series for AAPL (warm enough for all indicators)
RISES = [100.0 + i * 0.5 for i in range(60)]
# 60-bar flat series for 005930
FLAT = [60000.0] * 60


# ---------------------------------------------------------------------------
# buy_and_hold_return
# ---------------------------------------------------------------------------


def test_buy_and_hold_single_symbol_known_value():
    """Hand-computed: 100 → 110 = +10%."""
    bars = _bars_for(SYM_A, [100.0, 105.0, 110.0])
    result = buy_and_hold_return(bars)
    assert abs(result - 0.10) < 1e-9


def test_buy_and_hold_flat_is_zero():
    bars = _bars_for(SYM_A, [50.0, 50.0, 50.0])
    assert buy_and_hold_return(bars) == pytest.approx(0.0)


def test_buy_and_hold_multi_symbol_equal_weight():
    """Equal-weight average: (AAPL +10%, 005930 0%) = +5%."""
    bars_a = _bars_for(SYM_A, [100.0, 110.0])
    bars_b = _bars_for(SYM_B, [60000.0, 60000.0])
    all_bars = bars_a + bars_b
    result = buy_and_hold_return(all_bars)
    assert abs(result - 0.05) < 1e-9


# ---------------------------------------------------------------------------
# run_strategy
# ---------------------------------------------------------------------------


def _build_simple_strategy(portfolio: Portfolio, enter_threshold: float) -> FusionEngine:
    """Single MA source, wide window to ensure warmup with 60 bars."""
    src = TechnicalIndicatorSource(
        name="technical.ma_10_30", indicator=MovingAverageCross(10, 30)
    )
    return FusionEngine(
        [src],
        portfolio,
        RiskManager(0.3),
        OrderFactory(),
        enter_threshold=enter_threshold,
        source_weight={"technical.ma_10_30": 1.0},
    )


def test_run_strategy_returns_stats_and_curve():
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats, curve = run_strategy(all_bars, _build_simple_strategy, enter_threshold=0.10)

    assert isinstance(stats, StrategyStats)
    assert len(curve) == len(all_bars)
    assert all(isinstance(v, float) for v in curve)


def test_strategy_stats_invariants():
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats, _ = run_strategy(all_bars, _build_simple_strategy, enter_threshold=0.10)

    assert stats.trades >= 0
    assert 0.0 <= stats.exposure <= 1.0
    assert stats.avg_holding_days >= 0.0
    assert stats.final_equity_krw > 0.0


def test_strategy_that_never_fires_has_zero_trades_and_exposure():
    """With a very high threshold (2.0 → impossible score), no orders should fire."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    # enter_threshold=2.0 is beyond [-1,1] score range → no orders ever
    stats, curve = run_strategy(all_bars, _build_simple_strategy, enter_threshold=2.0)

    assert stats.trades == 0
    assert stats.exposure == pytest.approx(0.0)


def test_equity_curve_length_matches_bars():
    bars = _bars_for(SYM_A, [10.0 + i for i in range(40)])
    stats, curve = run_strategy(bars, _build_simple_strategy, enter_threshold=0.02)
    assert len(curve) == 40


def test_final_equity_matches_last_curve_value():
    bars_a = _bars_for(SYM_A, RISES)
    stats, curve = run_strategy(bars_a, _build_simple_strategy, enter_threshold=0.10)
    assert abs(stats.final_equity_krw - curve[-1]) < 1.0  # within 1 KRW rounding


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------


def test_evaluate_returns_structured_result():
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10, 0.35))

    assert "buy_and_hold" in result
    assert "strategies" in result
    strategies = result["strategies"]
    assert "single_avg" in strategies
    assert "diversified" in strategies

    # Each strategy has an entry per threshold
    for name in ("single_avg", "diversified"):
        for thr in (0.10, 0.35):
            key = f"thr={thr:.2f}"
            assert key in strategies[name], f"missing {name}/{key}"
            entry = strategies[name][key]
            assert "stats" in entry
            assert "equity_curve" in entry


def test_buy_and_hold_value_in_result():
    bars_a = _bars_for(SYM_A, [100.0, 110.0])
    bars_b = _bars_for(SYM_B, [60000.0, 60000.0])
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.35,))
    # Equal-weight buy-and-hold: (10% + 0%) / 2 = 5%
    assert abs(result["buy_and_hold"] - 0.05) < 1e-9


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_contains_disclaimer():
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10, 0.35))
    report = format_report(result)

    assert "DIAGNOSTIC ONLY" in report
    assert "statistically insignificant" in report
    assert "not optimized" in report.lower() or "not optim" in report.lower()


def test_format_report_contains_strategy_names():
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10, 0.35))
    report = format_report(result)

    assert "single_avg" in report
    assert "diversified" in report
    assert "buy_and_hold" in report or "Buy & Hold" in report


def test_format_report_contains_thresholds():
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10, 0.20, 0.35))
    report = format_report(result)

    assert "0.10" in report
    assert "0.20" in report
    assert "0.35" in report
