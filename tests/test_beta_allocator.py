# tests/test_beta_allocator.py
"""Tests for the single-instrument beta allocator — pure, no KIS."""
from __future__ import annotations

from trader.strategy.beta_allocator import latest_exposure, rebalance_order


# ---------------------------------------------------------------------------
# latest_exposure
# ---------------------------------------------------------------------------

def test_exposure_calm_uptrend_is_high():
    rets = [0.0005] * 300           # steady low-vol rise
    e = latest_exposure(rets, target_vol=0.15, trend_window=200)
    assert e > 0.8


def test_exposure_downtrend_goes_to_cash():
    rets = [0.002] * 250 + [-0.01] * 120   # uptrend then sustained downtrend
    e = latest_exposure(rets, target_vol=0.15, trend_window=100)
    assert e == 0.0                 # trend filter → cash


def test_exposure_empty_is_zero():
    assert latest_exposure([]) == 0.0


# ---------------------------------------------------------------------------
# rebalance_order
# ---------------------------------------------------------------------------

def test_buy_from_flat():
    # exposure 1.0, all cash, price 10000, equity 1,000,000 → target 100 shares
    d = rebalance_order(1.0, 10_000.0, 1_000_000.0, 0, rebalance_band=0.05)
    assert d["side"] == "BUY"
    assert d["qty"] == 100

def test_cash_goes_to_zero_exposure_sells_all():
    # hold 100 shares, exposure 0 → sell all
    d = rebalance_order(0.0, 10_000.0, 0.0, 100)
    assert d["side"] == "SELL"
    assert d["qty"] == 100
    assert d["target_shares"] == 0


def test_within_band_holds():
    # already ~at target → HOLD (no churn)
    d = rebalance_order(0.50, 10_000.0, 500_000.0, 50, rebalance_band=0.05)
    # equity = 500k cash + 50*10k = 1,000,000; target = 0.5*1e6/1e4 = 50 shares
    assert d["side"] == "HOLD"


def test_cannot_buy_more_than_cash_allows():
    # exposure 1.0 but only 300k cash + 0 shares, price 10000 → max 30 shares
    d = rebalance_order(1.0, 10_000.0, 300_000.0, 0, rebalance_band=0.01)
    assert d["side"] == "BUY"
    assert d["qty"] == 30
    assert d["target_shares"] == 30


def test_bad_price_holds():
    d = rebalance_order(1.0, 0.0, 1_000_000.0, 0)
    assert d["side"] == "HOLD"


# ---------------------------------------------------------------------------
# shared-equity sizing (2026-07-02 audit fix: no cross-sleeve double-count)
# ---------------------------------------------------------------------------

def test_explicit_equity_prevents_double_count():
    # true equity 1,000,000; sleeve holds 0 shares; stale-cash bug would have
    # seen cash 1,000,000 while ANOTHER sleeve already deployed 500,000.
    # With explicit equity, target = 0.5 * 1,000,000 = 50 shares (not 100).
    d = rebalance_order(0.5, 10_000.0, 500_000.0, 0,
                        equity_krw=1_000_000.0, rebalance_band=0.01)
    assert d["side"] == "BUY"
    assert d["qty"] == 50


def test_explicit_equity_sell_down_overdeployed():
    # sleeve holds 64 shares (640,000) but true shared equity is 1,000,000 and
    # target is 0.5 → 50 shares → SELL 14 (the SPY remediation case).
    d = rebalance_order(0.5, 10_000.0, 0.0, 64,
                        equity_krw=1_000_000.0, rebalance_band=0.05)
    assert d["side"] == "SELL"
    assert d["qty"] == 14


def test_buy_capped_by_true_cash_even_with_big_equity():
    # equity says buy 50 but only 200,000 real cash → afford 20
    d = rebalance_order(0.5, 10_000.0, 200_000.0, 0,
                        equity_krw=1_000_000.0, rebalance_band=0.01)
    assert d["side"] == "BUY"
    assert d["qty"] == 20


# ---------------------------------------------------------------------------
# robust_index_returns (coverage floor + partial-bar exclusion)
# ---------------------------------------------------------------------------

def _mk_panel(spec):
    """spec: {sym: [(date, close), ...]}"""
    from datetime import datetime, timezone
    from trader.core.events import BarEvent, Market, Symbol
    out = {}
    for sym, rows in spec.items():
        s = Symbol(sym, Market.KOSPI, "KRW")
        out[sym] = [BarEvent(s, datetime(d.year, d.month, d.day, tzinfo=timezone.utc),
                             c, c, c, c, 100) for d, c in rows]
    return out


def test_robust_index_skips_low_coverage_tail():
    from datetime import date
    from trader.strategy.beta_allocator import robust_index_returns
    d1, d2, d3 = date(2026, 6, 29), date(2026, 6, 30), date(2026, 7, 1)
    # 4 names on d1/d2 but only 1 name has d3 (ragged tail, 25% coverage)
    spec = {f"S{i}": [(d1, 100.0), (d2, 101.0)] for i in range(4)}
    spec["S0"].append((d3, 200.0))  # lone +98% garbage return
    rets = robust_index_returns(_mk_panel(spec), min_coverage=0.5)
    dates = [d for d, _ in rets]
    assert d3 not in dates            # ragged tail skipped
    assert d2 in dates                # full-coverage date kept


def test_robust_index_excludes_partial_today():
    from datetime import date
    from trader.strategy.beta_allocator import robust_index_returns
    d1, d2, today = date(2026, 6, 30), date(2026, 7, 1), date(2026, 7, 2)
    spec = {f"S{i}": [(d1, 100.0), (d2, 101.0), (today, 50.0)] for i in range(4)}
    rets = robust_index_returns(_mk_panel(spec), exclude_from=today)
    dates = [d for d, _ in rets]
    assert today not in dates         # partial intraday bar excluded
    assert d2 in dates
