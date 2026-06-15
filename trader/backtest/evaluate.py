# trader/backtest/evaluate.py
"""Descriptive strategy evaluation harness — ENGINE VALIDATION + SIGNAL DIAGNOSTICS ONLY.

CRITICAL: ~100 daily bars across 2 symbols is statistically insignificant.
This module validates that the engine runs correctly and shows how each signal
source behaves at different threshold sensitivity levels.  It does NOT and
CANNOT establish edge, alpha, Sharpe significance, or forward-looking returns.
Thresholds are a fixed pre-chosen sensitivity grid (0.10 / 0.20 / 0.35), never
optimised.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from trader.backtest.metrics import max_drawdown, total_return
from trader.core.events import BarEvent
from trader.execution.costs import MarketCostModel
from trader.execution.simulated import SimulatedExecutionHandler
from trader.signals.indicators import (
    BollingerReversion,
    MacdTrend,
    MovingAverageCross,
    RsiReversion,
)
from trader.signals.technical import TechnicalSignalSource
from trader.signals.technical_indicator_source import TechnicalIndicatorSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INITIAL_KRW = 10_000_000.0          # 10 M KRW starting capital
_FX_USD_KRW = 1380.0                  # fixed FX for backtest reproducibility
_COST_BPS = 5                         # 5 bps round-trip cost model

_DIVERSIFIED_SOURCE_WEIGHT = {
    "technical.ma_10_30":  0.30,
    "technical.rsi_14":    0.20,
    "technical.macd":      0.30,
    "technical.boll_20_2": 0.20,
}

_DISCLAIMER = """\
╔══════════════════════════════════════════════════════════════════════════════╗
║  DIAGNOSTIC ONLY — ENGINE VALIDATION & SIGNAL DIAGNOSTICS REPORT           ║
║                                                                              ║
║  ~100 bars / 2 symbols is statistically insignificant.  The numbers below   ║
║  validate that the engine executes correctly and show how each signal        ║
║  source BEHAVES at different sensitivity levels.  They do NOT establish      ║
║  edge, alpha, or Sharpe significance and are NOT a basis for trading         ║
║  decisions.                                                                  ║
║                                                                              ║
║  Thresholds shown (0.10 / 0.20 / 0.35) are a fixed pre-chosen sensitivity   ║
║  grid, explicitly diagnostic.  They are NEVER optimised — no parameter      ║
║  selection has been performed.                                               ║
╚══════════════════════════════════════════════════════════════════════════════╝"""


# ---------------------------------------------------------------------------
# StrategyStats dataclass
# ---------------------------------------------------------------------------

@dataclass
class StrategyStats:
    name: str
    trades: int                # number of fills (executions)
    total_return: float        # (final_equity / initial_equity) - 1
    max_drawdown: float        # negative fraction, e.g. -0.05 = -5%
    exposure: float            # fraction of bars where any position was held [0,1]
    avg_holding_days: float    # average length of each holding period in bars
    final_equity_krw: float    # absolute KRW equity at end


# ---------------------------------------------------------------------------
# buy_and_hold_return
# ---------------------------------------------------------------------------

def buy_and_hold_return(bars: list[BarEvent]) -> float:
    """Equal-weight buy-and-hold return across all symbols represented in bars.

    For each unique symbol: (last_close / first_close) - 1.
    Returns the equal-weight average across symbols.
    Returns 0.0 if bars is empty.
    """
    if not bars:
        return 0.0

    # Group by symbol
    by_sym: dict[tuple[str, str], list[BarEvent]] = {}
    for b in bars:
        key = (b.symbol.market.value, b.symbol.ticker)
        by_sym.setdefault(key, []).append(b)

    returns: list[float] = []
    for sym_bars in by_sym.values():
        sym_bars_sorted = sorted(sym_bars, key=lambda b: b.ts)
        first = sym_bars_sorted[0].close
        last = sym_bars_sorted[-1].close
        if first > 0:
            returns.append(last / first - 1.0)

    if not returns:
        return 0.0
    return sum(returns) / len(returns)


# ---------------------------------------------------------------------------
# run_strategy
# ---------------------------------------------------------------------------

def _make_portfolio() -> tuple[Portfolio, FxRates]:
    fx = FxRates({"USD": _FX_USD_KRW, "KRW": 1.0})
    pf = Portfolio({"KRW": _INITIAL_KRW}, fx)
    return pf, fx


def run_strategy(
    bars: list[BarEvent],
    build_strategy: Callable[[Portfolio, float], FusionEngine],
    *,
    enter_threshold: float,
) -> tuple[StrategyStats, list[float]]:
    """Run a single strategy configuration over bars and collect diagnostics.

    Event loop order (matches BacktestEngine / LiveEngine for parity):
      1. execution.on_bar(bar) → fills
      2. strategy.on_fill(fill) + portfolio.apply_fill(fill) [via FusionEngine.on_fill]
      3. portfolio.mark(bar)
      4. strategy.on_bar(bar) → orders
      5. execution.submit_order(order)

    Args:
        bars: All BarEvents, unsorted is fine — sorted internally by (ts, ticker).
        build_strategy: Factory callable(portfolio, enter_threshold) → FusionEngine.
        enter_threshold: Signal threshold to pass to build_strategy.

    Returns:
        (StrategyStats, equity_curve_krw)  where equity_curve has one entry per bar.
    """
    pf, _ = _make_portfolio()
    strategy = build_strategy(pf, enter_threshold)
    execution = SimulatedExecutionHandler(MarketCostModel())

    sorted_bars = sorted(bars, key=lambda b: (b.ts, b.symbol.ticker))
    n_bars = len(sorted_bars)

    equity_curve: list[float] = []
    fills_count = 0

    # For exposure / holding-period tracking: track per-bar total open position count
    bars_with_position = 0

    # Holding-period tracking: symbol -> bar-index when position was opened
    _open_since: dict[tuple[str, str], int] = {}
    _holding_lengths: list[int] = []
    _bar_idx = 0

    for bar in sorted_bars:
        # Phase 1: fill pending orders at today's open
        for fill in execution.on_bar(bar):
            strategy.on_fill(fill)
            fills_count += 1

        # Phase 2: mark-to-market at close
        pf.mark(bar)

        # Phase 3: strategy decides orders based on close
        orders = strategy.on_bar(bar)
        for order in orders:
            execution.submit_order(order)

        # Track equity
        eq = pf.equity_krw()
        equity_curve.append(eq)

        # Track exposure: any nonzero position this bar?
        open_count = pf.open_position_count()
        if open_count > 0:
            bars_with_position += 1

        # Track per-symbol holding periods (open / close transitions)
        for sym_bars_key, qty in list(pf._pos.items()):
            was_open = sym_bars_key in _open_since
            is_open = qty != 0
            if is_open and not was_open:
                _open_since[sym_bars_key] = _bar_idx
            elif not is_open and was_open:
                _holding_lengths.append(_bar_idx - _open_since.pop(sym_bars_key))

        _bar_idx += 1

    # Close any still-open positions at end for holding-period calc
    for sym_key, opened_at in _open_since.items():
        _holding_lengths.append(n_bars - opened_at)

    exposure = bars_with_position / n_bars if n_bars > 0 else 0.0
    avg_holding = sum(_holding_lengths) / len(_holding_lengths) if _holding_lengths else 0.0

    stats = StrategyStats(
        name=f"thr={enter_threshold:.2f}",
        trades=fills_count,
        total_return=total_return(equity_curve),
        max_drawdown=max_drawdown(equity_curve),
        exposure=exposure,
        avg_holding_days=avg_holding,
        final_equity_krw=pf.equity_krw(),
    )
    return stats, equity_curve


# ---------------------------------------------------------------------------
# Strategy factories
# ---------------------------------------------------------------------------

def _build_single_avg(portfolio: Portfolio, enter_threshold: float) -> FusionEngine:
    """TechnicalSignalSource(20,50) wrapped so FusionEngine source_weight={"technical":1}."""
    src = TechnicalSignalSource(fast=20, slow=50)
    return FusionEngine(
        [src],
        portfolio,
        RiskManager(max_symbol_weight=0.30),
        OrderFactory(),
        enter_threshold=enter_threshold,
        source_weight={"technical": 1.0},
    )


def _build_diversified(portfolio: Portfolio, enter_threshold: float) -> FusionEngine:
    """4 TechnicalIndicatorSource instances with the run_daily SOURCE_WEIGHT."""
    sources = [
        TechnicalIndicatorSource(name="technical.ma_10_30", indicator=MovingAverageCross(10, 30)),
        TechnicalIndicatorSource(name="technical.rsi_14",   indicator=RsiReversion(14, 30, 70)),
        TechnicalIndicatorSource(name="technical.macd",     indicator=MacdTrend(12, 26, 9)),
        TechnicalIndicatorSource(name="technical.boll_20_2",indicator=BollingerReversion(20, 2.0)),
    ]
    return FusionEngine(
        sources,
        portfolio,
        RiskManager(max_symbol_weight=0.30),
        OrderFactory(),
        enter_threshold=enter_threshold,
        source_weight=_DIVERSIFIED_SOURCE_WEIGHT,
    )


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------

def evaluate(
    bars: list[BarEvent],
    thresholds: tuple[float, ...] = (0.10, 0.20, 0.35),
) -> dict:
    """Run both strategies across the threshold grid and compute buy-and-hold.

    Returns a structured dict::

        {
            "buy_and_hold": float,
            "strategies": {
                "single_avg": {
                    "thr=0.10": {"stats": StrategyStats, "equity_curve": list[float]},
                    ...
                },
                "diversified": { ... },
            },
            "n_bars": int,
            "thresholds": tuple,
        }
    """
    named_factories: dict[str, Callable[[Portfolio, float], FusionEngine]] = {
        "single_avg": _build_single_avg,
        "diversified": _build_diversified,
    }

    strategies_result: dict[str, dict] = {}
    for strat_name, factory in named_factories.items():
        thr_results: dict[str, dict] = {}
        for thr in thresholds:
            stats, curve = run_strategy(bars, factory, enter_threshold=thr)
            stats.name = strat_name  # override with strategy name
            thr_results[f"thr={thr:.2f}"] = {
                "stats": stats,
                "equity_curve": curve,
            }
        strategies_result[strat_name] = thr_results

    return {
        "buy_and_hold": buy_and_hold_return(bars),
        "strategies": strategies_result,
        "n_bars": len(bars),
        "thresholds": thresholds,
    }


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------

def format_report(result: dict) -> str:
    """Format a human-readable diagnostic report from evaluate() output.

    Includes the MANDATORY disclaimer block.
    """
    lines: list[str] = []
    lines.append("")
    lines.append(_DISCLAIMER)
    lines.append("")

    n_bars = result.get("n_bars", "?")
    thresholds = result.get("thresholds", ())
    bnh = result["buy_and_hold"]

    lines.append(f"  Total bars in dataset : {n_bars}")
    lines.append(f"  Thresholds (fixed grid): {', '.join(f'{t:.2f}' for t in thresholds)}")
    lines.append(f"  Initial capital        : {_INITIAL_KRW:,.0f} KRW")
    lines.append(f"  Cost model             : MarketCostModel (KOSPI 1.41bps+20bps sell tax; NASDAQ 25bps+SEC+TAF)")
    lines.append(f"  FX rate (fixed)        : 1 USD = {_FX_USD_KRW:,.1f} KRW")
    lines.append("")

    # ── Buy & Hold reference ────────────────────────────────────────────────
    lines.append("  Buy & Hold (equal-weight, no costs)")
    lines.append(f"    Return : {bnh:+.2%}")
    lines.append("")

    # ── Per-strategy table ──────────────────────────────────────────────────
    col_w = 10
    strategies = result.get("strategies", {})

    for strat_name, thr_map in strategies.items():
        lines.append(f"  Strategy: {strat_name}")
        lines.append(
            f"  {'Threshold':>10} {'Trades':>7} {'Return':>9} {'MaxDD':>9} "
            f"{'Exposure':>9} {'AvgHold':>8} {'FinalEq(M KRW)':>15}"
        )
        lines.append("  " + "-" * 75)
        for thr_key in sorted(thr_map.keys()):
            entry = thr_map[thr_key]
            s: StrategyStats = entry["stats"]
            final_m = s.final_equity_krw / 1_000_000
            lines.append(
                f"  {thr_key:>10} {s.trades:>7d} {s.total_return:>+9.2%} "
                f"{s.max_drawdown:>+9.2%} {s.exposure:>9.2%} "
                f"{s.avg_holding_days:>8.1f} {final_m:>15.4f}"
            )
        lines.append("")

    lines.append(
        "  NOTE: 'Trades' = number of fills (each buy or sell = 1 trade)."
    )
    lines.append(
        "  'Exposure' = fraction of bars where at least one position was open."
    )
    lines.append(
        "  'AvgHold' = average holding period in bars (trading days)."
    )
    lines.append("")
    lines.append(
        "  These numbers are DIAGNOSTIC ONLY.  Do not draw conclusions about"
    )
    lines.append(
        "  strategy quality.  Thresholds are not optimized — they are a"
    )
    lines.append(
        "  fixed pre-chosen sensitivity grid for engine validation purposes."
    )
    lines.append("")

    return "\n".join(lines)
