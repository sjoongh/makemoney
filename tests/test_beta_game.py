# tests/test_beta_game.py
"""Tests for the risk-managed beta-game backtest — synthetic, no network."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trader.core.events import BarEvent, Market, Symbol
from trader.research.beta_game import ew_daily_returns, run_beta_game

_START = datetime(2016, 1, 1, tzinfo=timezone.utc)


def _panel(closes_by_ticker: dict[str, list[float]]) -> dict[str, list[BarEvent]]:
    out = {}
    for tk, closes in closes_by_ticker.items():
        sym = Symbol(tk, Market.NASDAQ, "USD")
        out[tk] = [
            BarEvent(sym, _START + timedelta(days=i), c, c, c, c, 1000)
            for i, c in enumerate(closes)
        ]
    return out


def test_ew_daily_returns_basic():
    panel = _panel({"A": [100, 110], "B": [100, 90]})  # +10% and -10% → EW 0%
    r = ew_daily_returns(panel)
    assert len(r) == 1
    assert abs(r[0][1] - 0.0) < 1e-9


def test_vol_target_cuts_drawdown_in_a_crash():
    # calm uptrend then a violent crash; vol targeting should reduce MaxDD
    closes = [100.0]
    for _ in range(60):
        closes.append(closes[-1] * 1.003)         # calm low-vol rise
    for _ in range(40):
        closes.append(closes[-1] * (0.93 if len(closes) % 2 else 1.04))  # volatile crash
    panel = _panel({"A": closes, "B": closes})
    res = run_beta_game(panel, target_vol=0.12)
    s, b = res["strategy"], res["benchmark"]
    # risk-managed beta should have a shallower drawdown than naive buy&hold
    assert s["max_drawdown"] > b["max_drawdown"]   # less negative = shallower
    assert 0.0 < res["avg_exposure"] <= 1.0


def test_trend_filter_exits_before_sustained_crash():
    # long uptrend then a sustained downtrend; the trend filter should move to
    # cash and avoid most of the bear market → much shallower drawdown.
    closes = [100.0]
    for _ in range(250):
        closes.append(closes[-1] * 1.002)    # long bull
    for _ in range(120):
        closes.append(closes[-1] * 0.99)     # sustained bear
    panel = _panel({"A": closes, "B": closes})
    defended = run_beta_game(panel, target_vol=0.15, trend_window=100)
    plain = run_beta_game(panel, target_vol=0.15)  # no trend filter
    # trend-filtered strategy avoids most of the downtrend → shallower MaxDD
    assert defended["strategy"]["max_drawdown"] > plain["strategy"]["max_drawdown"]
    assert defended["time_in_market"] < 1.0     # spent time in cash


def test_flat_calm_market_exposure_high():
    # steady low-vol rise → vol targeting wants full (capped) exposure
    closes = [100.0 * (1.0005 ** i) for i in range(120)]
    panel = _panel({"A": closes, "B": closes})
    res = run_beta_game(panel, target_vol=0.12)
    assert res["avg_exposure"] > 0.8
    assert res["n_days"] == 119
