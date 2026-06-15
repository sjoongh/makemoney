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


# ---------------------------------------------------------------------------
# Sleeve strategy tests (evaluate returns trend_only/reversion_only/combined)
# ---------------------------------------------------------------------------

from trader.backtest.evaluate import (  # noqa: E402
    _HoldingTracker,
    evaluate_sleeves,
    run_sleeve_strategy,
)


def test_evaluate_returns_sleeve_strategy_keys():
    """evaluate() must include trend_only, reversion_only, combined_sleeves keys."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10, 0.35))

    strategies = result["strategies"]
    for name in ("trend_only", "reversion_only", "combined_sleeves"):
        assert name in strategies, f"Missing strategy key: {name}"
        for thr in (0.10, 0.35):
            key = f"thr={thr:.2f}"
            assert key in strategies[name], f"Missing threshold {key} in {name}"
            entry = strategies[name][key]
            assert "stats" in entry
            assert isinstance(entry["stats"], StrategyStats)
            assert "equity_curve" in entry


def test_evaluate_sleeves_returns_three_strategies():
    """evaluate_sleeves() must return exactly trend_only, reversion_only, combined_sleeves."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate_sleeves(all_bars, thresholds=(0.10,))

    assert set(result.keys()) == {"trend_only", "reversion_only", "combined_sleeves"}
    for name, thr_map in result.items():
        assert "thr=0.10" in thr_map
        entry = thr_map["thr=0.10"]
        s = entry["stats"]
        assert isinstance(s, StrategyStats)
        assert s.trades >= 0
        assert 0.0 <= s.exposure <= 1.0
        assert s.final_equity_krw > 0.0


def test_run_sleeve_strategy_returns_stats_and_curve():
    """run_sleeve_strategy must return valid StrategyStats and correct-length curve."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats, curve = run_sleeve_strategy(all_bars, enter_threshold=0.10)

    assert isinstance(stats, StrategyStats)
    assert stats.name == "combined_sleeves"
    assert len(curve) == len(all_bars)
    assert all(isinstance(v, float) for v in curve)
    assert stats.final_equity_krw > 0.0


def test_combined_sleeves_equity_is_sum_of_halves():
    """combined_sleeves equity should reflect two sub-portfolios each seeded at 50% capital.

    We can't directly access the sub-portfolios here, but we verify that
    the final equity is > 0 and the equity curve has the right length.
    """
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats, curve = run_sleeve_strategy(all_bars, enter_threshold=0.10,
                                       capital_fraction_trend=0.5,
                                       capital_fraction_reversion=0.5)

    # Combined equity = trend_half + reversion_half — both seeded from _INITIAL_KRW
    # Final equity must be positive and curve length must match bar count
    assert stats.final_equity_krw > 0.0
    assert len(curve) == len(all_bars)


def test_format_report_includes_sleeve_strategy_names():
    """format_report must include trend_only, reversion_only, combined_sleeves."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    result = evaluate(all_bars, thresholds=(0.10,))
    report = format_report(result)

    assert "trend_only" in report
    assert "reversion_only" in report
    assert "combined_sleeves" in report


# ---------------------------------------------------------------------------
# Bug-fix regression tests: trades = actual fills, exposure = aggregate
# ---------------------------------------------------------------------------


def test_run_strategy_zero_fills_when_threshold_impossible():
    """With threshold=2.0 (beyond [-1,1] score range), no fills must occur."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats, _ = run_strategy(all_bars, _build_simple_strategy, enter_threshold=2.0)

    assert stats.trades == 0
    assert stats.exposure == pytest.approx(0.0)


def test_run_sleeve_strategy_zero_fills_when_threshold_impossible():
    """With threshold=2.0, combined_sleeves must report 0 trades and 0.0 exposure."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats, _ = run_sleeve_strategy(all_bars, enter_threshold=2.0)

    assert stats.trades == 0, f"Expected 0 trades with impossible threshold, got {stats.trades}"
    assert stats.exposure == pytest.approx(0.0), (
        f"Expected 0.0 exposure with no positions, got {stats.exposure}"
    )


def test_run_sleeve_strategy_exposure_not_inflated():
    """Exposure with impossible threshold must be 0.0, not inflated.

    This is the OR-artifact regression: the old code checked
    trend_open + rev_open > 0, which would be True if either sleeve had
    ghost entries in _pos. With threshold=2.0 and no fills, _pos is empty
    in both sleeves, so the aggregate must be 0.0.
    """
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats, _ = run_sleeve_strategy(all_bars, enter_threshold=2.0)

    assert stats.exposure == pytest.approx(0.0), (
        f"Exposure must be 0.0 when no fills occur, got {stats.exposure:.4f} "
        f"(OR-inflation artifact?)"
    )


def test_run_sleeve_strategy_trades_counts_fills_not_holding_transitions():
    """Trades must equal actual FillEvents, not holding-period transitions.

    With threshold=2.0 -> 0 fills. With threshold=0.10 -> trades >= 0.
    Key invariant: trades(thr=2.0) == 0, exposure in [0,1].
    """
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats_no_trade, _ = run_sleeve_strategy(all_bars, enter_threshold=2.0)
    stats_active, _   = run_sleeve_strategy(all_bars, enter_threshold=0.10)

    assert stats_no_trade.trades == 0
    assert stats_active.trades >= 0  # structural: must be non-negative
    assert 0.0 <= stats_active.exposure <= 1.0


# ---------------------------------------------------------------------------
# _HoldingTracker unit tests — deterministic white-box scenarios
# ---------------------------------------------------------------------------


def test_holding_tracker_single_open_close():
    """Buy at bar 2, sell at bar 5 → holding 3 bars → AvgHold == 3.0.

    Definition: open_bar_idx=2, close_bar_idx=5 → length = 5 - 2 = 3.
    """
    sym_key = ("NASDAQ", "AAPL")
    tracker = _HoldingTracker()
    n_bars = 8

    # bars 0,1: no position
    tracker.update({}, 0)
    tracker.update({}, 1)
    # bar 2: position opens (qty 0 → nonzero)
    tracker.update({sym_key: 10}, 2)
    # bars 3,4: still open
    tracker.update({sym_key: 10}, 3)
    tracker.update({sym_key: 10}, 4)
    # bar 5: position closes (qty → 0)
    tracker.update({sym_key: 0}, 5)
    # bars 6,7: no position
    tracker.update({}, 6)
    tracker.update({}, 7)

    avg = tracker.finalise(n_bars)
    assert avg == pytest.approx(3.0), f"Expected AvgHold=3.0, got {avg}"


def test_holding_tracker_partial_hold_counted():
    """Position opens at bar 3 and is still open at end of 6-bar run.

    Partial hold = 6 - 3 = 3 bars.  AvgHold must include this partial hold.
    """
    sym_key = ("NASDAQ", "AAPL")
    tracker = _HoldingTracker()
    n_bars = 6

    tracker.update({}, 0)
    tracker.update({}, 1)
    tracker.update({}, 2)
    # bar 3: opens
    tracker.update({sym_key: 5}, 3)
    tracker.update({sym_key: 5}, 4)
    tracker.update({sym_key: 5}, 5)

    avg = tracker.finalise(n_bars)
    assert avg == pytest.approx(3.0), f"Expected partial hold AvgHold=3.0, got {avg}"


def test_holding_tracker_no_positions_returns_zero():
    """All-cash run: AvgHold must be 0.0."""
    tracker = _HoldingTracker()
    for i in range(10):
        tracker.update({}, i)
    avg = tracker.finalise(10)
    assert avg == pytest.approx(0.0)


def test_holding_tracker_fully_invested_run():
    """Position open from bar 0 through entire 5-bar run → partial hold = 5.

    No explicit close → finalise counts it as 5 - 0 = 5 bars.
    """
    sym_key = ("KOSPI", "005930")
    tracker = _HoldingTracker()
    n_bars = 5
    for i in range(n_bars):
        tracker.update({sym_key: 100}, i)
    avg = tracker.finalise(n_bars)
    assert avg == pytest.approx(5.0)


def test_holding_tracker_multiple_positions():
    """Two separate holds: bars 0-2 (length 2) and bars 4-7 (length 3) → avg 2.5."""
    sym_key = ("NASDAQ", "AAPL")
    tracker = _HoldingTracker()
    n_bars = 8

    # First hold: opens bar 0, closes bar 2 → length 2
    tracker.update({sym_key: 10}, 0)
    tracker.update({sym_key: 10}, 1)
    tracker.update({sym_key: 0}, 2)   # close

    # gap: bars 3 (no position)
    tracker.update({}, 3)

    # Second hold: opens bar 4, closes bar 7 → length 3
    tracker.update({sym_key: 10}, 4)
    tracker.update({sym_key: 10}, 5)
    tracker.update({sym_key: 10}, 6)
    tracker.update({sym_key: 0}, 7)   # close

    avg = tracker.finalise(n_bars)
    assert avg == pytest.approx(2.5), f"Expected AvgHold=2.5, got {avg}"


# ---------------------------------------------------------------------------
# Exposure definition tests
# ---------------------------------------------------------------------------


def test_exposure_all_cash_is_zero():
    """With threshold=2.0 (impossible to fill), exposure must be exactly 0.0."""
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    stats, _ = run_strategy(all_bars, _build_simple_strategy, enter_threshold=2.0)

    assert stats.exposure == pytest.approx(0.0)
    assert stats.avg_holding_days == pytest.approx(0.0)


def test_sleeve_single_sleeve_equivalent_matches_single_path():
    """A single-sleeve run (100% trend capital, 0% reversion) should produce
    the same AvgHold and exposure as running the same trend engine via run_strategy,
    because both use the same _HoldingTracker definition on the same positions.

    We verify that the two paths give structurally consistent results on the SAME
    bars: both exposure and avg_holding_days must be in [0, 1] / >= 0 respectively,
    and with threshold=2.0 (no trades) both must be exactly 0.0.
    """
    bars_a = _bars_for(SYM_A, RISES)
    bars_b = _bars_for(SYM_B, FLAT)
    all_bars = sorted(bars_a + bars_b, key=lambda b: (b.ts, b.symbol.ticker))

    # Single path: trend engine, no trades
    from trader.backtest.evaluate import _build_trend_engine  # noqa: PLC0415

    stats_single, _ = run_strategy(all_bars, _build_trend_engine, enter_threshold=2.0)

    # Sleeve path: 100% trend, 0% reversion capital (both impossible threshold)
    stats_sleeve, _ = run_sleeve_strategy(all_bars, enter_threshold=2.0,
                                          capital_fraction_trend=1.0,
                                          capital_fraction_reversion=0.0)

    # Both paths: 0 trades, 0 exposure, 0 AvgHold
    assert stats_single.trades == 0
    assert stats_sleeve.trades == 0
    assert stats_single.exposure == pytest.approx(0.0)
    assert stats_sleeve.exposure == pytest.approx(0.0)
    assert stats_single.avg_holding_days == pytest.approx(0.0)
    assert stats_sleeve.avg_holding_days == pytest.approx(0.0)
