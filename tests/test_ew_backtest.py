# tests/test_ew_backtest.py
"""Tests for the clean equal-weight backtest — RESEARCH ONLY, no network.

The headline regression test (test_uptrending_benchmark_is_positive) is exactly
the check the old research/momentum.py benchmark FAILED: an equal-weight basket
of names that all rise must produce a POSITIVE benchmark return.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trader.core.events import BarEvent, Market, Symbol
from trader.research.ew_backtest import run_ew_backtest

_START = datetime(2016, 1, 1, tzinfo=timezone.utc)


def _panel(drifts: list[float], n_days: int = 700) -> dict[str, list[BarEvent]]:
    out: dict[str, list[BarEvent]] = {}
    for k, g in enumerate(drifts):
        sym = Symbol(f"S{k:03d}", Market.NASDAQ, "USD")
        bars = []
        for d in range(n_days):
            ts = _START + timedelta(days=d)
            close = 100.0 * (1.0 + g) ** d
            bars.append(BarEvent(sym, ts, close, close + 1, close - 1, close, 1000))
        out[f"S{k:03d}"] = bars
    return out


def test_uptrending_benchmark_is_positive():
    """REGRESSION: every symbol rises ~+0.05%/day → equal-weight benchmark MUST
    be strongly positive. (The old momentum.py benchmark reported negative here.)"""
    panel = _panel([0.0005] * 30, n_days=760)  # ~+13%/yr each
    res = run_ew_backtest(panel, lookback=252, skip=21)
    assert res["benchmark_metrics"]["cagr"] > 0.05
    assert res["benchmark_equity"][-1][1] > res["benchmark_equity"][0][1]


def test_flat_market_benchmark_near_zero():
    panel = _panel([0.0] * 20, n_days=760)
    res = run_ew_backtest(panel, lookback=252, skip=21)
    assert abs(res["benchmark_metrics"]["cagr"]) < 0.02


def test_momentum_holds_top_performers():
    # distinct positive drifts; top-k momentum should beat (or match) the basket
    drifts = [0.0001 * (k + 1) for k in range(30)]  # 0.0001 .. 0.0030
    panel = _panel(drifts, n_days=760)
    res = run_ew_backtest(panel, lookback=252, skip=21, top_pct=0.1, min_k=3, max_k=5)
    # strategy concentrates in the highest-drift names → should beat equal-weight
    assert res["strategy_metrics"]["cagr"] > res["benchmark_metrics"]["cagr"]


def test_single_currency_sane_magnitudes():
    panel = _panel([0.0003] * 25, n_days=760)
    res = run_ew_backtest(panel, lookback=252, skip=21)
    # no impossible drawdowns from accounting bugs
    assert 0.0 <= res["benchmark_metrics"]["max_dd"] < 0.5
    assert res["n_months"] > 10
