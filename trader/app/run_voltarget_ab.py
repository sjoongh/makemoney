# trader/app/run_voltarget_ab.py
"""A/B evaluation: portfolio volatility targeting OFF vs ON.

Runs the SAME diversified strategy on the SAME Samsung (005930) 5-year daily
data with vol_targeter=None (baseline) and vol_targeter=PortfolioVolTargeter()
(target_vol=0.12, lambda=0.94, min_obs=20).

Reports Sharpe / CAGR / MaxDD / Calmar / realized-vol for both, plus differences.

Metrics definitions
-------------------
- CAGR      : (final/initial)^(252/n_bars) - 1  (annualised from daily bars)
- MaxDD     : most negative trough/peak drawdown fraction (e.g. -0.15 = -15%)
- Realized vol: std(daily log-returns) * sqrt(252)
- Sharpe    : mean(daily ret) / std(daily ret) * sqrt(252)  (0% risk-free rate)
- Calmar    : CAGR / abs(MaxDD)  (inf if MaxDD==0)

Usage
-----
    .venv/bin/python -m trader.app.run_voltarget_ab
    # or
    .venv/bin/python trader/app/run_voltarget_ab.py [path/to/parquet]
"""
from __future__ import annotations

import math
import sys
from typing import Callable

from trader.backtest.evaluate import _INITIAL_KRW, _FX_USD_KRW, _DIVERSIFIED_SOURCE_WEIGHT
from trader.core.events import BarEvent
from trader.data.storage import load_bars
from trader.execution.costs import MarketCostModel
from trader.execution.simulated import SimulatedExecutionHandler
from trader.signals.indicators import (
    BollingerReversion,
    MacdTrend,
    MovingAverageCross,
    RsiReversion,
)
from trader.signals.technical_indicator_source import TechnicalIndicatorSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager
from trader.strategy.vol_target import PortfolioVolTargeter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_PARQUET = "research_data/KOSPI_005930.parquet"
_ENTER_THRESHOLD = 0.35


# ---------------------------------------------------------------------------
# Strategy factories
# ---------------------------------------------------------------------------

def _make_portfolio() -> tuple[Portfolio, FxRates]:
    fx = FxRates({"USD": _FX_USD_KRW, "KRW": 1.0})
    pf = Portfolio({"KRW": _INITIAL_KRW}, fx)
    return pf, fx


def _build_diversified(
    portfolio: Portfolio,
    vol_targeter: PortfolioVolTargeter | None,
) -> FusionEngine:
    sources = [
        TechnicalIndicatorSource(
            name="technical.ma_10_30", indicator=MovingAverageCross(10, 30)
        ),
        TechnicalIndicatorSource(
            name="technical.rsi_14", indicator=RsiReversion(14, 30, 70)
        ),
        TechnicalIndicatorSource(
            name="technical.macd", indicator=MacdTrend(12, 26, 9)
        ),
        TechnicalIndicatorSource(
            name="technical.boll_20_2", indicator=BollingerReversion(20, 2.0)
        ),
    ]
    return FusionEngine(
        sources,
        portfolio,
        RiskManager(max_symbol_weight=0.30),
        OrderFactory(),
        enter_threshold=_ENTER_THRESHOLD,
        source_weight=_DIVERSIFIED_SOURCE_WEIGHT,
        vol_targeter=vol_targeter,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run(
    bars: list[BarEvent],
    vol_targeter: PortfolioVolTargeter | None,
) -> dict:
    """Run the diversified strategy and return performance metrics."""
    pf, _ = _make_portfolio()
    strategy = _build_diversified(pf, vol_targeter)
    execution = SimulatedExecutionHandler(MarketCostModel())

    sorted_bars = sorted(bars, key=lambda b: (b.ts, b.symbol.ticker))
    n_bars = len(sorted_bars)

    equity_curve: list[float] = [_INITIAL_KRW]

    for bar in sorted_bars:
        for fill in execution.on_bar(bar):
            strategy.on_fill(fill)
        pf.mark(bar)
        for order in strategy.on_bar(bar):
            execution.submit_order(order)
        equity_curve.append(pf.equity_krw())

    # Remove the leading sentinel if we injected one
    if equity_curve[0] == _INITIAL_KRW and len(equity_curve) > 1:
        equity_curve = equity_curve[1:]

    return _metrics(equity_curve, n_bars)


def _metrics(equity_curve: list[float], n_bars: int) -> dict:
    if len(equity_curve) < 2:
        return {"CAGR": 0.0, "MaxDD": 0.0, "Sharpe": 0.0, "Calmar": 0.0, "Vol": 0.0}

    initial = equity_curve[0]
    final = equity_curve[-1]

    # Daily log returns
    log_rets = [
        math.log(equity_curve[i] / equity_curve[i - 1])
        for i in range(1, len(equity_curve))
        if equity_curve[i - 1] > 0 and equity_curve[i] > 0
    ]

    n = len(log_rets)
    if n == 0:
        return {"CAGR": 0.0, "MaxDD": 0.0, "Sharpe": 0.0, "Calmar": 0.0, "Vol": 0.0}

    mean_r = sum(log_rets) / n
    var_r = sum((r - mean_r) ** 2 for r in log_rets) / max(n - 1, 1)
    std_r = math.sqrt(var_r)

    vol_ann = std_r * math.sqrt(252)
    sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0

    # CAGR from equity levels (arithmetic)
    years = n_bars / 252.0
    cagr = (final / initial) ** (1.0 / years) - 1.0 if years > 0 and initial > 0 else 0.0

    # Max drawdown
    peak = equity_curve[0]
    mdd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            dd = (v - peak) / peak
            mdd = min(mdd, dd)

    calmar = cagr / abs(mdd) if mdd != 0 else float("inf")

    return {
        "CAGR": cagr,
        "MaxDD": mdd,
        "Sharpe": sharpe,
        "Calmar": calmar,
        "Vol": vol_ann,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _fmt(val: float, pct: bool = False) -> str:
    if math.isinf(val):
        return "    inf"
    if pct:
        return f"{val:+7.2%}"
    return f"{val:+7.4f}"


def print_ab_report(off: dict, on: dict) -> None:
    metrics = ["Sharpe", "CAGR", "MaxDD", "Calmar", "Vol"]
    hdr = f"{'Metric':<10} {'Vol-Target OFF':>15} {'Vol-Target ON':>15} {'Delta (ON-OFF)':>15}"
    sep = "-" * len(hdr)

    print()
    print("=" * len(hdr))
    print("  PORTFOLIO VOLATILITY TARGETING  A/B  —  Samsung (005930) 5yr daily")
    print("  Strategy: diversified (MA-cross + RSI + MACD + Bollinger), thr=0.35")
    print(f"  Vol-target params: target_vol=0.12, lambda=0.94, min_obs=20")
    print("=" * len(hdr))
    print(hdr)
    print(sep)

    pct_metrics = {"CAGR", "MaxDD", "Vol"}
    for m in metrics:
        v_off = off[m]
        v_on = on[m]
        delta = v_on - v_off
        is_pct = m in pct_metrics
        print(
            f"  {m:<8} {_fmt(v_off, is_pct):>15} {_fmt(v_on, is_pct):>15} {_fmt(delta, is_pct):>15}"
        )

    print(sep)
    print()

    # Honest interpretation
    sharpe_improved = on["Sharpe"] > off["Sharpe"]
    calmar_improved = on["Calmar"] > off["Calmar"]
    dd_improved = abs(on["MaxDD"]) < abs(off["MaxDD"])

    print("  HONEST READ:")
    print(f"    Sharpe   {'IMPROVED' if sharpe_improved else 'DEGRADED'} "
          f"({off['Sharpe']:+.4f} → {on['Sharpe']:+.4f})")
    print(f"    Calmar   {'IMPROVED' if calmar_improved else 'DEGRADED'} "
          f"({off['Calmar']:+.4f} → {on['Calmar']:+.4f})")
    print(f"    MaxDD    {'IMPROVED (smaller)' if dd_improved else 'DEGRADED (larger)'} "
          f"({off['MaxDD']:+.2%} → {on['MaxDD']:+.2%})")

    if sharpe_improved and calmar_improved and dd_improved:
        verdict = "Vol targeting HELPED on all three risk-adjusted metrics."
    elif sharpe_improved or calmar_improved:
        verdict = "Vol targeting gave MIXED results — some metrics improved, some degraded."
    else:
        verdict = ("Vol targeting did NOT improve risk-adjusted returns on this dataset. "
                   "May simply smooth vol at a return cost.")
    print(f"    Verdict: {verdict}")
    print()
    print("  CAVEATS: Single symbol, ~5yr daily bars. Statistically insufficient")
    print("  to draw forward-looking conclusions. These numbers validate engine")
    print("  behaviour only — not edge or alpha.")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(parquet_path: str = _DEFAULT_PARQUET) -> None:
    bars = load_bars(parquet_path)
    print(f"  Loaded {len(bars)} bars from {parquet_path}")

    off_metrics = _run(bars, vol_targeter=None)
    on_metrics = _run(bars, vol_targeter=PortfolioVolTargeter(
        target_vol=0.12, lam=0.94, min_obs=20
    ))

    print_ab_report(off_metrics, on_metrics)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else _DEFAULT_PARQUET
    main(path)
