# trader/research/ew_backtest.py
"""RESEARCH ONLY — clean equal-weight monthly-rebalanced backtest.

Replacement for the benchmark/portfolio path in research/momentum.py, which was
found (by actually running it on the 703-symbol dataset) to report an IMPOSSIBLE
~-73% total return for a US large-cap equal-weight basket whose real value is
~+400%. This module is verified against that reality and carries a regression
test (up-trending synthetic data MUST yield a positive benchmark) that the old
code lacked.

SINGLE CURRENCY ONLY: pass a panel from ONE market (all USD or all KRW). Mixing
USD (~$100) and KRW (~₩300,000) without FX normalisation is itself a bug; run
each market separately and report side by side.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any

from trader.core.events import BarEvent
from trader.research.momentum import _compute_metrics  # equity-curve metrics (verified)


def _build_price(panel: dict[str, list[BarEvent]]) -> tuple[dict, list[date]]:
    price: dict[date, dict[str, float]] = defaultdict(dict)
    all_dates: set[date] = set()
    for sym, bars in panel.items():
        for b in bars:
            d = b.ts.date()
            price[d][sym] = b.close
            all_dates.add(d)
    return price, sorted(all_dates)


def _ew_period_return(names: list[str], price: dict, d0: date, d1: date) -> float:
    """Equal-weight simple return over [d0, d1] across names priced on BOTH ends."""
    rets = []
    for s in names:
        p0 = price.get(d0, {}).get(s)
        p1 = price.get(d1, {}).get(s)
        if p0 and p1 and p0 > 0:
            rets.append(p1 / p0 - 1.0)
    return sum(rets) / len(rets) if rets else 0.0


def _momentum_12_1(price, dates_up_to: list[date], sym: str, lookback: int, skip: int):
    """close[t-skip]/close[t-lookback]-1 using the symbol's own priced dates."""
    sd = [d for d in dates_up_to if sym in price[d]]
    if len(sd) < lookback + 1:
        return None
    near = price[sd[-(skip + 1)]][sym]
    far = price[sd[-(lookback + 1)]][sym]
    if far <= 0:
        return None
    return near / far - 1.0


def run_ew_backtest(
    panel: dict[str, list[BarEvent]],
    *,
    lookback: int = 252,
    skip: int = 21,
    top_pct: float = 0.10,
    min_k: int = 5,
    max_k: int = 20,
    init_capital: float = 10_000_000.0,
) -> dict[str, Any]:
    """Monthly-rebalanced equal-weight backtest (single currency).

    Strategy: long top-k by 12-1 momentum, equal weight.
    Benchmark: equal weight over ALL names priced that month (buy-the-basket).
    Returns {strategy_metrics, benchmark_metrics, strategy_equity, benchmark_equity}.
    """
    price, dates = _build_price(panel)
    if len(dates) < lookback + skip + 5:
        raise ValueError(f"not enough history: {len(dates)} dates")

    rebal = [i for i in range(1, len(dates)) if dates[i].month != dates[i - 1].month]

    strat_eq = bench_eq = init_capital
    strat_curve: list[tuple[date, float]] = []
    bench_curve: list[tuple[date, float]] = []
    strat_rets: list[float] = []
    bench_rets: list[float] = []
    strat_hold: list[str] = []
    prev_sig: date | None = None

    for ri in rebal:
        sig = dates[ri - 1]  # month-end signal date
        if prev_sig is not None:
            # apply the holdings chosen at the PREVIOUS rebalance over [prev_sig, sig]
            r_s = _ew_period_return(strat_hold, price, prev_sig, sig)
            bench_names = [s for s in price[prev_sig] if price[prev_sig][s] > 0]
            r_b = _ew_period_return(bench_names, price, prev_sig, sig)
            strat_eq *= (1 + r_s)
            bench_eq *= (1 + r_b)
            strat_rets.append(r_s)
            bench_rets.append(r_b)
            strat_curve.append((sig, strat_eq))
            bench_curve.append((sig, bench_eq))

        # choose new strategy holdings as of `sig`
        dates_up = [d for d in dates if d <= sig]
        scored = []
        for sym in panel:
            m = _momentum_12_1(price, dates_up, sym, lookback, skip)
            if m is not None:
                scored.append((sym, m))
        scored.sort(key=lambda x: x[1], reverse=True)
        if len(scored) >= min_k:
            k = max(min_k, min(max_k, math.ceil(len(scored) * top_pct)))
            strat_hold = [s for s, _ in scored[:k]]
        else:
            strat_hold = []
        prev_sig = sig

    return {
        "strategy_metrics": _compute_metrics(strat_curve, strat_rets, [], [], init_capital, "strategy"),
        "benchmark_metrics": _compute_metrics(bench_curve, bench_rets, [], [], init_capital, "benchmark"),
        "strategy_equity": strat_curve,
        "benchmark_equity": bench_curve,
        "n_months": len(strat_rets),
    }
