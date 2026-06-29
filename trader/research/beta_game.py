# trader/research/beta_game.py
"""RESEARCH ONLY — the honest "beta game": risk-managed market exposure.

No alpha was found (see RESEARCH_CONCLUSION.md). The defensible alternative is to
OWN THE MARKET with risk management: hold the equal-weight universe but scale
gross exposure by EWMA volatility targeting, so the portfolio cuts deep drawdowns
in turbulent regimes (the unallocated fraction sits in cash). This does NOT beat
the market on raw return; it aims for a better RISK-ADJUSTED profile (Sharpe,
MaxDD) — pure beta, honestly managed.

Look-ahead-safe: the exposure applied to the [t, t+1] return is decided using
only returns through t.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from trader.core.events import BarEvent
from trader.strategy.vol_target import PortfolioVolTargeter


def ew_daily_returns(panel: dict[str, list[BarEvent]]) -> list[tuple[date, float]]:
    """Equal-weight market daily simple return: mean across names priced on both
    consecutive trading days. Returns ascending [(date, ret)]."""
    price: dict[str, dict[date, float]] = {}
    all_dates: set[date] = set()
    for sym, bars in panel.items():
        m = {b.ts.date(): b.close for b in bars}
        price[sym] = m
        all_dates.update(m)
    dates = sorted(all_dates)
    out: list[tuple[date, float]] = []
    for i in range(1, len(dates)):
        d0, d1 = dates[i - 1], dates[i]
        rets = []
        for sym, m in price.items():
            p0, p1 = m.get(d0), m.get(d1)
            if p0 and p1 and p0 > 0:
                rets.append(p1 / p0 - 1.0)
        if rets:
            out.append((d1, sum(rets) / len(rets)))
    return out


def _metrics(daily: list[float]) -> dict:
    a = np.asarray(daily, dtype=float)
    n = len(a)
    if n == 0:
        return {"cagr": 0.0, "ann_vol": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    eq = np.cumprod(1.0 + a)
    cagr = float(eq[-1] ** (252.0 / n) - 1.0)
    sd = a.std(ddof=1) if n > 1 else 0.0
    ann_vol = float(sd * np.sqrt(252))
    sharpe = float(a.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    peak = np.maximum.accumulate(eq)
    max_dd = float((eq / peak - 1.0).min())
    return {"cagr": cagr, "ann_vol": ann_vol, "sharpe": sharpe, "max_drawdown": max_dd}


def run_beta_game(
    panel: dict[str, list[BarEvent]],
    *,
    target_vol: float = 0.12,
    max_leverage: float = 1.0,
) -> dict:
    """Backtest risk-managed beta (vol-targeted EW) vs naive buy&hold EW.

    Returns {"strategy": metrics, "benchmark": metrics, "n_days": int,
             "avg_exposure": float}.
    """
    rets = ew_daily_returns(panel)
    if len(rets) < 30:
        raise ValueError("not enough data for beta-game backtest")

    targeter = PortfolioVolTargeter(target_vol=target_vol, max_scalar=max_leverage)
    mkt_equity = 1.0
    targeter.update(mkt_equity)  # seed with day 0

    strat: list[float] = []
    bench: list[float] = []
    exposures: list[float] = []
    for _d, r in rets:
        exposure = min(targeter.scalar(), max_leverage)  # decided from returns through prev day
        strat.append(exposure * r)
        bench.append(r)
        exposures.append(exposure)
        mkt_equity *= (1.0 + r)
        targeter.update(mkt_equity)  # include this day for the NEXT decision

    return {
        "strategy": _metrics(strat),       # vol-targeted (risk-managed beta)
        "benchmark": _metrics(bench),      # naive buy&hold EW
        "n_days": len(rets),
        "avg_exposure": float(np.mean(exposures)),
        "target_vol": target_vol,
    }
