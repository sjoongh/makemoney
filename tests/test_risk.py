# tests/test_risk.py
"""TDD tests for enhanced RiskManager."""
from __future__ import annotations
from datetime import datetime, timezone, date
from uuid import uuid4

import pytest

from trader.core.events import Symbol, Market, BarEvent, FillEvent, Side, TargetPosition
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
SYM2 = Symbol("MSFT", Market.NASDAQ, "USD")
KRW_SYM = Symbol("005930", Market.KOSPI, "KRW")

# ── helpers ──────────────────────────────────────────────────────────────────

def _ts(day: int = 1) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)

def _bar(sym: Symbol, close: float, high: float | None = None,
         low: float | None = None, day: int = 1) -> BarEvent:
    h = high if high is not None else close
    l = low if low is not None else close
    return BarEvent(sym, _ts(day), close, h, l, close, 100)

def _fill(sym: Symbol, qty: int, price: float, ccy: str, day: int = 1) -> FillEvent:
    return FillEvent(uuid4(), sym, _ts(day), Side.BUY, qty, price, 0.0, ccy)

def _simple_portfolio(equity_krw: float = 1_000_000.0) -> Portfolio:
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    return Portfolio({"KRW": equity_krw}, fx)

def _target(sym: Symbol = SYM, weight: float = 0.5, reason: str = "") -> TargetPosition:
    return TargetPosition(sym, weight, reason)


# ── Backward-compatible: existing intent preserved ────────────────────────────

def test_clamps_to_max_weight_and_no_short():
    """Old-style call: size_target with just a TargetPosition (no portfolio/bar)."""
    pf = _simple_portfolio()
    bar = _bar(SYM, 100.0)
    rm = RiskManager(max_symbol_weight=0.3)
    assert rm.size_target(_target(weight=0.9), pf, bar).target_weight == pytest.approx(0.3)
    assert rm.size_target(_target(weight=-0.5), pf, bar).target_weight == 0.0


def test_kill_switch_forces_flat():
    pf = _simple_portfolio()
    bar = _bar(SYM, 100.0)
    rm = RiskManager(max_symbol_weight=0.3)
    rm.trip_kill_switch()
    assert rm.size_target(_target(weight=0.9), pf, bar).target_weight == 0.0


def test_kill_switch_reason_contains_kill():
    pf = _simple_portfolio()
    bar = _bar(SYM, 100.0)
    rm = RiskManager(max_symbol_weight=0.3)
    rm.trip_kill_switch()
    result = rm.size_target(_target(weight=0.9), pf, bar)
    assert "kill" in result.reason.lower()


def test_zero_target_weight_returns_zero():
    pf = _simple_portfolio()
    bar = _bar(SYM, 100.0)
    rm = RiskManager(max_symbol_weight=0.3)
    assert rm.size_target(_target(weight=0.0), pf, bar).target_weight == 0.0


# ── ATR vol scaling ──────────────────────────────────────────────────────────

def _feed_atr_bars(rm: RiskManager, pf: Portfolio, sym: Symbol,
                   atr_period: int, close: float, tr: float) -> BarEvent:
    """
    Feed atr_period bars to warm up ATR.
    Each bar has high=close+tr/2, low=close-tr/2 so True Range ≈ tr
    (first bar has no prev_close so TR = high-low = tr).
    Returns the last bar fed.
    """
    bar = None
    for i in range(atr_period):
        bar = BarEvent(sym, _ts(i + 1), close, close + tr / 2, close - tr / 2, close, 100)
        rm.on_bar(bar, pf)
    return bar


def test_vol_scaling_halves_weight_when_atr_double_target():
    """
    When atr/close = 2 * target_atr_pct, the scaling factor = 0.5.
    raw weight 0.5 → after clamp (max=0.5) = 0.5 → after vol scaling = 0.25.
    """
    target_atr_pct = 0.03
    atr_period = 5  # small period for test speed
    rm = RiskManager(max_symbol_weight=0.5, atr_period=atr_period,
                     target_atr_pct=target_atr_pct)
    pf = _simple_portfolio()

    # close=100, tr=6 → atr≈6, atr_pct=0.06 = 2*target → scale=0.5
    close = 100.0
    tr = 6.0  # atr_pct = 0.06 = 2 * 0.03
    last_bar = _feed_atr_bars(rm, pf, SYM, atr_period, close, tr)

    result = rm.size_target(_target(weight=0.5), pf, last_bar)
    # min(0.5, max=0.5) = 0.5; scale = 0.03/0.06 = 0.5; final = 0.25
    assert result.target_weight == pytest.approx(0.25, rel=1e-6)


def test_vol_scaling_no_effect_when_atr_below_target():
    """When atr_pct <= target_atr_pct, scale=1.0 (min(1, target/atr) >= 1)."""
    target_atr_pct = 0.03
    atr_period = 5
    rm = RiskManager(max_symbol_weight=0.5, atr_period=atr_period,
                     target_atr_pct=target_atr_pct)
    pf = _simple_portfolio()

    # close=100, tr=1 → atr≈1, atr_pct=0.01 < 0.03 → scale=min(1,3)=1
    close = 100.0
    tr = 1.0
    last_bar = _feed_atr_bars(rm, pf, SYM, atr_period, close, tr)

    result = rm.size_target(_target(weight=0.4), pf, last_bar)
    # clamp: min(0.4, 0.5)=0.4; scale=min(1, 0.03/0.01)=1.0; final=0.4
    assert result.target_weight == pytest.approx(0.4, rel=1e-6)


def test_no_vol_scaling_when_atr_not_warmed():
    """With fewer bars than atr_period, no ATR → no scaling."""
    rm = RiskManager(max_symbol_weight=0.5, atr_period=14, target_atr_pct=0.03)
    pf = _simple_portfolio()
    # Feed only 5 bars (< atr_period=14)
    for i in range(5):
        bar = _bar(SYM, 100.0, high=110.0, low=90.0, day=i + 1)
        rm.on_bar(bar, pf)
    last_bar = _bar(SYM, 100.0, day=6)
    result = rm.size_target(_target(weight=0.4), pf, last_bar)
    # No ATR available → no scaling → just clamp
    assert result.target_weight == pytest.approx(0.4, rel=1e-6)


# ── Daily loss limit ──────────────────────────────────────────────────────────

def test_daily_loss_limit_trips_daily_killed():
    """
    If equity falls more than daily_loss_limit_pct from day start,
    _daily_killed is set and size_target returns 0.
    """
    rm = RiskManager(daily_loss_limit_pct=0.03)
    # Start with equity=1,000,000. Day-start is set on first bar.
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 1_000_000.0}, fx)

    # First bar of day 1 → sets day_start_equity = 1,000,000
    bar1 = _bar(SYM, 100.0, day=1)
    rm.on_bar(bar1, pf)

    # Simulate loss: drain cash so equity = 960,000 (4% drop > 3% limit)
    pf.cash["KRW"] = 960_000.0

    # Second bar on same day → checks daily loss
    bar2 = _bar(SYM, 100.0, day=1)
    rm.on_bar(bar2, pf)

    bar3 = _bar(SYM, 100.0, day=1)
    result = rm.size_target(_target(weight=0.5), pf, bar3)
    assert result.target_weight == 0.0
    assert "kill" in result.reason.lower()


def test_daily_loss_limit_resets_next_day():
    """_daily_killed resets at the start of a new day."""
    rm = RiskManager(daily_loss_limit_pct=0.03)
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 1_000_000.0}, fx)

    # Day 1: trigger daily kill
    bar1 = _bar(SYM, 100.0, day=1)
    rm.on_bar(bar1, pf)
    pf.cash["KRW"] = 960_000.0  # 4% loss
    bar2 = _bar(SYM, 100.0, day=1)
    rm.on_bar(bar2, pf)
    assert rm._daily_killed is True

    # Day 2: new day → reset
    bar3 = _bar(SYM, 100.0, day=2)
    rm.on_bar(bar3, pf)
    assert rm._daily_killed is False

    result = rm.size_target(_target(weight=0.5), pf, bar3)
    # No permanent kill, equity is fine on day2 start (960k resets)
    assert result.target_weight > 0.0


def test_daily_loss_limit_no_trip_within_limit():
    """A loss smaller than daily_loss_limit_pct does not trip."""
    rm = RiskManager(daily_loss_limit_pct=0.03)
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 1_000_000.0}, fx)

    bar1 = _bar(SYM, 100.0, day=1)
    rm.on_bar(bar1, pf)

    # 2% loss (< 3% limit) → should NOT trip
    pf.cash["KRW"] = 980_000.0
    bar2 = _bar(SYM, 100.0, day=1)
    rm.on_bar(bar2, pf)

    result = rm.size_target(_target(weight=0.5), pf, bar2)
    assert result.target_weight > 0.0


# ── Max positions ─────────────────────────────────────────────────────────────

def test_max_positions_blocks_new_symbol_at_cap():
    """When at max_positions and symbol not already held, weight→0."""
    rm = RiskManager(max_positions=1)
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 3_000_000.0}, fx)

    # Already hold SYM (1 open position)
    pf.apply_fill(_fill(SYM, 10, 100.0, "USD"))
    pf.mark(_bar(SYM, 100.0))

    bar = _bar(SYM2, 50.0)
    result = rm.size_target(_target(SYM2, weight=0.3), pf, bar)
    assert result.target_weight == 0.0


def test_max_positions_allows_already_held_symbol():
    """A symbol already in portfolio can be sized even at max_positions."""
    rm = RiskManager(max_positions=1)
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 3_000_000.0}, fx)

    pf.apply_fill(_fill(SYM, 10, 100.0, "USD"))
    pf.mark(_bar(SYM, 100.0))

    bar = _bar(SYM, 100.0)
    result = rm.size_target(_target(SYM, weight=0.3), pf, bar)
    assert result.target_weight > 0.0


def test_max_positions_none_is_no_op():
    """max_positions=None (default) never blocks."""
    rm = RiskManager(max_positions=None)
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 3_000_000.0}, fx)
    for i in range(20):
        sym = Symbol(f"SYM{i}", Market.NASDAQ, "USD")
        pf.apply_fill(_fill(sym, 1, 100.0, "USD"))
        pf.mark(_bar(sym, 100.0))

    bar = _bar(SYM2, 50.0)
    result = rm.size_target(_target(SYM2, weight=0.2), pf, bar)
    assert result.target_weight > 0.0


# ── Market cap weight ─────────────────────────────────────────────────────────

def test_market_cap_clamps_weight():
    """
    max_market_weight for NASDAQ=0.4. If current NASDAQ weight=0.3 and
    we request 0.2 more, result clamped to 0.1 (so total stays ≤ 0.4).
    """
    rm = RiskManager(max_symbol_weight=0.5,
                     max_market_weight={Market.NASDAQ: 0.4})
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    # equity=1,000,000 KRW; hold 10 AAPL@100 USD → pos_value = 1,300,000
    # That's already > equity, so let's use a bigger portfolio
    # equity=10,000,000 KRW; hold 10 AAPL@100 USD → pos_value=1,300,000 → weight=0.13
    # Want AAPL weight=0.13, ask for SYM2=0.3 → market would be 0.43 > 0.4
    # clamp: w = min(0.3, max(0, 0.4 - (0.13 - 0))) = min(0.3, 0.27) = 0.27
    pf = Portfolio({"KRW": 10_000_000.0}, fx)
    pf.apply_fill(_fill(SYM, 10, 100.0, "USD"))
    pf.mark(_bar(SYM, 100.0))

    bar = _bar(SYM2, 50.0)
    result = rm.size_target(_target(SYM2, weight=0.3), pf, bar)

    # AAPL pos_value=1,300,000; equity after fill = 10,000,000-1,300,000+1,300,000=10,000,000
    # market_weight(NASDAQ) = 1,300,000/10,000,000 = 0.13
    # SYM2 has no position, so position_weight(SYM2)=0
    # available = 0.4 - (0.13 - 0) = 0.27
    # clamped_w = min(0.3, max(0, 0.27)) = 0.27
    assert result.target_weight == pytest.approx(0.27, rel=1e-6)


def test_market_cap_allows_within_cap():
    """If market is well under cap, no clamping occurs."""
    rm = RiskManager(max_symbol_weight=0.5,
                     max_market_weight={Market.NASDAQ: 0.9})
    pf = _simple_portfolio(1_000_000.0)
    bar = _bar(SYM, 100.0)
    result = rm.size_target(_target(weight=0.3), pf, bar)
    assert result.target_weight == pytest.approx(0.3, rel=1e-6)


def test_market_cap_not_set_for_market_is_no_op():
    """max_market_weight only applies to markets explicitly in the dict."""
    rm = RiskManager(max_symbol_weight=0.5,
                     max_market_weight={Market.KOSPI: 0.1})
    pf = _simple_portfolio(1_000_000.0)
    bar = _bar(SYM, 100.0)  # NASDAQ, not in dict
    result = rm.size_target(_target(weight=0.4), pf, bar)
    assert result.target_weight == pytest.approx(0.4, rel=1e-6)
