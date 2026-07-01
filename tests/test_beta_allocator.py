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
