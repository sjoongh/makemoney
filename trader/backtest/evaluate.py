# trader/backtest/evaluate.py
"""Descriptive strategy evaluation harness — ENGINE VALIDATION + SIGNAL DIAGNOSTICS ONLY.

CRITICAL: ~100 daily bars across 2 symbols is statistically insignificant.
This module validates that the engine runs correctly and shows how each signal
source behaves at different threshold sensitivity levels.  It does NOT and
CANNOT establish edge, alpha, Sharpe significance, or forward-looking returns.
Thresholds are a fixed pre-chosen sensitivity grid (0.10 / 0.20 / 0.35), never
optimised.

Two-sleeve strategies (trend_only, reversion_only, combined_sleeves) are added
via evaluate_sleeves() and merged into the main evaluate() result dict so that
all strategies can be compared side-by-side in format_report().
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from trader.backtest.metrics import max_drawdown, total_return
from trader.core.events import BarEvent
from trader.execution.costs import MarketCostModel
from trader.research.disclaimers import SURVIVORSHIP_WARNING
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
from trader.strategy.sleeve import MultiSleeveEngine, StrategySleeve

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
║  Daily bars across 2 symbols is statistically insignificant even at ~500    ║
║  bars.  The numbers below validate that the engine executes correctly and   ║
║  show how each signal source BEHAVES at different sensitivity levels.  They ║
║  do NOT establish edge, alpha, or Sharpe significance and are NOT a basis   ║
║  for trading decisions.                                                      ║
║                                                                              ║
║  Thresholds shown (0.10 / 0.20 / 0.35) are a fixed pre-chosen sensitivity  ║
║  grid, explicitly diagnostic.  They are NEVER optimised — no parameter     ║
║  selection has been performed.                                               ║
║                                                                              ║
║  Sleeve strategies (trend_only / reversion_only / combined_sleeves) show    ║
║  BEHAVIOURAL separation only — NOT optimised allocation or signal tuning.   ║
╚══════════════════════════════════════════════════════════════════════════════╝"""


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def equal_weight_buyhold(
    bars_by_symbol: dict[str, list[BarEvent]],
) -> tuple[list[float], dict]:
    """Compute an equal-weight buy-and-hold equity curve and summary metrics.

    Each symbol receives 1/N of the initial capital (_INITIAL_KRW) at bar 0
    and is held to the end without rebalancing.  No transaction costs are
    modelled (gross benchmark).

    This gives the return of simply owning the ENTIRE opportunity set that
    the strategy was allowed to trade, which is a more informative baseline
    than a single-stock buy-and-hold when evaluating multi-symbol strategies.

    NOTE: if an externally-provided market-index return series is available
    (e.g. SPY or KOSPI index), supply it directly rather than this function —
    that removes the same survivorship bias that affects the strategy universe.
    See docs/data-limitations.md.

    Args:
        bars_by_symbol: dict mapping symbol name → list[BarEvent] (any order).
                        Each symbol's bars are sorted internally by timestamp.

    Returns:
        (curve, metrics) where:
          curve   — list[float] equity values at each unique date (ascending),
                    one entry per unique date across all symbols.
          metrics — dict with keys: total_return (float), n_symbols (int),
                    n_dates (int).  Returns zeros/empty if no bars provided.
    """
    if not bars_by_symbol:
        return [], {"total_return": 0.0, "n_symbols": 0, "n_dates": 0}

    # Collect all unique timestamps (sorted)
    all_ts: list = sorted({b.ts for bars in bars_by_symbol.values() for b in bars})
    n_dates = len(all_ts)
    n_syms = len(bars_by_symbol)
    if n_syms == 0 or n_dates == 0:
        return [], {"total_return": 0.0, "n_symbols": 0, "n_dates": 0}

    capital_per_sym = _INITIAL_KRW / n_syms

    # Build per-symbol price lookup: ts → close
    price_by_sym: dict[str, dict] = {}
    first_close: dict[str, float] = {}
    for sym, bars in bars_by_symbol.items():
        sorted_bars = sorted(bars, key=lambda b: b.ts)
        price_by_sym[sym] = {b.ts: b.close for b in sorted_bars}
        first_close[sym] = sorted_bars[0].close if sorted_bars else 0.0

    curve: list[float] = []
    for ts in all_ts:
        equity = 0.0
        for sym in bars_by_symbol:
            px0 = first_close[sym]
            px1 = price_by_sym[sym].get(ts)
            if px0 and px0 > 0 and px1 is not None:
                equity += capital_per_sym * (px1 / px0)
            else:
                # Symbol not yet started or price missing → hold at cost basis
                equity += capital_per_sym
        curve.append(equity)

    total_ret = (curve[-1] / _INITIAL_KRW - 1.0) if curve else 0.0
    metrics = {
        "total_return": total_ret,
        "n_symbols": n_syms,
        "n_dates": n_dates,
    }
    return curve, metrics


# ---------------------------------------------------------------------------
# _HoldingTracker — shared helper for AvgHold computation
# ---------------------------------------------------------------------------

class _HoldingTracker:
    """Track per-symbol holding periods from actual position 0→nonzero entries/exits.

    Definition (applied identically to run_strategy and run_sleeve_strategy):
      - A position OPENS on the bar where a symbol's net qty transitions from 0 to nonzero.
      - A position CLOSES on the bar where a symbol's net qty transitions from nonzero to 0.
      - Holding length = (close_bar_idx - open_bar_idx), measured in bars.
      - A position still open at end-of-run counts its bars held so far:
        holding = (n_bars - open_bar_idx).  This partial hold IS included in AvgHold.
      - AvgHold = mean of all completed + partial holding lengths.  0.0 if no positions.

    Exposure definition (tracked externally per bar, not here):
      - Fraction of bar-events where the (aggregate) book holds any nonzero net position.
      - For the single path: any nonzero position in the single portfolio.
      - For the sleeve path: union of both sleeve portfolios — counted ONCE per bar
        (not OR-inflated across sleeves; the check is a single boolean per bar event).
    """

    def __init__(self) -> None:
        self._open_since: dict[tuple[str, str], int] = {}  # sym_key -> bar_idx when opened
        self._holding_lengths: list[int] = []

    def update(self, pos_dict: dict[tuple[str, str], int], bar_idx: int) -> None:
        """Inspect a portfolio's _pos dict and record open/close transitions.

        Call once per bar per portfolio, AFTER the portfolio has been marked and
        orders submitted (i.e. at end-of-bar processing, when _pos reflects
        positions as of end of this bar's signal cycle — fills from THIS bar
        already applied, new orders from THIS bar's signal are pending for next bar).

        Args:
            pos_dict: The portfolio's _pos dict {(market, ticker): qty}.
            bar_idx:  Zero-based index of the current bar in the sorted bar list.
        """
        for key, qty in list(pos_dict.items()):
            was_open = key in self._open_since
            is_open = qty != 0
            if is_open and not was_open:
                # Position opened this bar (qty went 0 → nonzero)
                self._open_since[key] = bar_idx
            elif not is_open and was_open:
                # Position closed this bar (qty went nonzero → 0)
                self._holding_lengths.append(bar_idx - self._open_since.pop(key))

    def finalise(self, n_bars: int) -> float:
        """Close any still-open positions and return AvgHold.

        Positions still open at end-of-run are counted with bars held so far:
        holding = n_bars - open_bar_idx (partial hold included in the average).

        Args:
            n_bars: Total number of bars in the run.

        Returns:
            Average holding period in bars (0.0 if no positions were ever held).
        """
        for opened_at in self._open_since.values():
            self._holding_lengths.append(n_bars - opened_at)
        return (
            sum(self._holding_lengths) / len(self._holding_lengths)
            if self._holding_lengths
            else 0.0
        )


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
    bars_with_position = 0   # bars where portfolio holds any nonzero position
    tracker = _HoldingTracker()
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

        # Exposure: any nonzero position this bar? (checked once per bar)
        if pf.open_position_count() > 0:
            bars_with_position += 1

        # Holding-period: detect open/close transitions via shared tracker
        tracker.update(pf._pos, _bar_idx)
        _bar_idx += 1

    exposure = bars_with_position / n_bars if n_bars > 0 else 0.0
    avg_holding = tracker.finalise(n_bars)

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
# Sleeve strategy factories (two-sleeve architecture)
# ---------------------------------------------------------------------------

_TREND_SOURCE_WEIGHT = {
    "technical.ma_10_30": 0.50,
    "technical.macd":     0.50,
}

_REVERSION_SOURCE_WEIGHT = {
    "technical.rsi_14":    0.50,
    "technical.boll_20_2": 0.50,
}


def _build_trend_engine(portfolio: Portfolio, enter_threshold: float) -> FusionEngine:
    """Trend sleeve: MA-cross + MACD only — no mean-reversion sources."""
    sources = [
        TechnicalIndicatorSource(name="technical.ma_10_30", indicator=MovingAverageCross(10, 30)),
        TechnicalIndicatorSource(name="technical.macd",     indicator=MacdTrend(12, 26, 9)),
    ]
    return FusionEngine(
        sources,
        portfolio,
        RiskManager(max_symbol_weight=0.30),
        OrderFactory(),
        enter_threshold=enter_threshold,
        source_weight=_TREND_SOURCE_WEIGHT,
    )


def _build_reversion_engine(portfolio: Portfolio, enter_threshold: float) -> FusionEngine:
    """Reversion sleeve: RSI-reversion + Bollinger-reversion only — no trend sources."""
    sources = [
        TechnicalIndicatorSource(name="technical.rsi_14",   indicator=RsiReversion(14, 30, 70)),
        TechnicalIndicatorSource(name="technical.boll_20_2", indicator=BollingerReversion(20, 2.0)),
    ]
    return FusionEngine(
        sources,
        portfolio,
        RiskManager(max_symbol_weight=0.30),
        OrderFactory(),
        enter_threshold=enter_threshold,
        source_weight=_REVERSION_SOURCE_WEIGHT,
    )


# ---------------------------------------------------------------------------
# run_sleeve_strategy — mirrors run_strategy but for MultiSleeveEngine
# ---------------------------------------------------------------------------

def run_sleeve_strategy(
    bars: list[BarEvent],
    enter_threshold: float,
    *,
    capital_fraction_trend: float = 0.5,
    capital_fraction_reversion: float = 0.5,
) -> tuple[StrategyStats, list[float]]:
    """Run the combined two-sleeve engine (trend + reversion, 50/50 capital).

    Event loop mirrors run_strategy exactly:
      1. execution.on_bar(bar) → fills → route to sleeve → fills_count += len(fills)
      2. mark each sleeve portfolio at close
      3. check aggregate position (union of both sleeve _pos): exposure tracking
      4. each sleeve.on_bar(bar) → orders → submit
      5. track aggregate equity = Σ sleeve.equity_krw()

    trades = number of FillEvents received (same definition as run_strategy).
    exposure = fraction of bars where the aggregate combined book holds any nonzero
               position in any symbol (computed from union of sleeve _pos dicts).

    Args:
        bars: All BarEvents (unsorted ok; sorted internally by ts, ticker).
        enter_threshold: Signal threshold for both sleeves.
        capital_fraction_trend: Fraction of _INITIAL_KRW seeded into trend sleeve.
        capital_fraction_reversion: Fraction of _INITIAL_KRW seeded into reversion sleeve.

    Returns:
        (StrategyStats, equity_curve_krw) one entry per bar.
    """
    fx = FxRates({"USD": _FX_USD_KRW, "KRW": 1.0})

    pf_trend = Portfolio({"KRW": _INITIAL_KRW * capital_fraction_trend}, fx)
    pf_rev   = Portfolio({"KRW": _INITIAL_KRW * capital_fraction_reversion}, fx)

    trend_engine = _build_trend_engine(pf_trend, enter_threshold)
    rev_engine   = _build_reversion_engine(pf_rev, enter_threshold)

    trend_sleeve = StrategySleeve("trend",     trend_engine, capital_fraction_trend)
    rev_sleeve   = StrategySleeve("reversion", rev_engine,   capital_fraction_reversion)

    sleeves = [trend_sleeve, rev_sleeve]
    execution = SimulatedExecutionHandler(MarketCostModel())

    # order_id → sleeve routing table (mirrors MultiSleeveEngine._order_sleeve)
    _order_sleeve: dict = {}

    sorted_bars = sorted(bars, key=lambda b: (b.ts, b.symbol.ticker))
    n_bars = len(sorted_bars)

    equity_curve: list[float] = []
    fills_count = 0          # actual FillEvents received (= trades)
    bars_with_position = 0   # bars where aggregate book has any nonzero position

    # One _HoldingTracker per sleeve portfolio — same definition as run_strategy
    tracker_trend = _HoldingTracker()
    tracker_rev   = _HoldingTracker()
    _bar_idx = 0

    for bar in sorted_bars:
        # ── Phase 1: fill pending orders at bar open ─────────────────────────
        fills = execution.on_bar(bar)
        for fill in fills:
            fills_count += 1                          # count ACTUAL fills
            sleeve = _order_sleeve.pop(fill.order_id, None)
            if sleeve is not None:
                sleeve.apply_fill(fill)

        # ── Phase 2: mark-to-market at close ─────────────────────────────────
        for sleeve in sleeves:
            sleeve.portfolio.mark(bar)

        # ── Exposure: aggregate nonzero position in any sleeve ────────────────
        # Union of both sleeve books — checked ONCE per bar (not OR-inflated).
        # A bar counts as "exposed" if EITHER sleeve holds any nonzero position.
        has_position = (pf_trend.open_position_count() > 0 or
                        pf_rev.open_position_count() > 0)
        if has_position:
            bars_with_position += 1

        # ── Equity tracking ───────────────────────────────────────────────────
        eq = sum(s.portfolio.equity_krw() for s in sleeves)
        equity_curve.append(eq)

        # ── Phase 3: each sleeve signals and submits orders ───────────────────
        for sleeve in sleeves:
            orders = sleeve.on_bar(bar)
            for order in orders:
                _order_sleeve[order.order_id] = sleeve
                execution.submit_order(order)

        # ── Holding-period tracking — one tracker per sleeve (same definition) ─
        tracker_trend.update(pf_trend._pos, _bar_idx)
        tracker_rev.update(pf_rev._pos, _bar_idx)
        _bar_idx += 1

    # Finalise both trackers: merge their holding lengths into a combined average
    avg_trend = tracker_trend.finalise(n_bars)
    avg_rev   = tracker_rev.finalise(n_bars)
    # Weighted average by number of completed+partial holds recorded
    all_lengths = tracker_trend._holding_lengths + tracker_rev._holding_lengths
    avg_holding = sum(all_lengths) / len(all_lengths) if all_lengths else 0.0

    exposure = bars_with_position / n_bars if n_bars > 0 else 0.0
    final_equity = sum(s.portfolio.equity_krw() for s in sleeves)

    stats = StrategyStats(
        name="combined_sleeves",
        trades=fills_count,
        total_return=total_return(equity_curve),
        max_drawdown=max_drawdown(equity_curve),
        exposure=exposure,
        avg_holding_days=avg_holding,
        final_equity_krw=final_equity,
    )
    return stats, equity_curve


# ---------------------------------------------------------------------------
# evaluate_sleeves
# ---------------------------------------------------------------------------

def evaluate_sleeves(
    bars: list[BarEvent],
    thresholds: tuple[float, ...] = (0.10, 0.20, 0.35),
) -> dict[str, dict]:
    """Run trend_only, reversion_only, combined_sleeves across the threshold grid.

    Returns a dict keyed by strategy name, each value a dict of
    {f"thr={thr:.2f}": {"stats": StrategyStats, "equity_curve": list[float]}}.
    """
    # trend_only: full capital seeded into trend sleeve; no reversion sleeve
    def _build_trend_only(portfolio: Portfolio, enter_threshold: float) -> FusionEngine:
        return _build_trend_engine(portfolio, enter_threshold)

    # reversion_only: full capital seeded into reversion sleeve; no trend sleeve
    def _build_reversion_only(portfolio: Portfolio, enter_threshold: float) -> FusionEngine:
        return _build_reversion_engine(portfolio, enter_threshold)

    result: dict[str, dict] = {}

    # trend_only and reversion_only use run_strategy (single FusionEngine, full capital)
    for strat_name, factory in [
        ("trend_only",      _build_trend_only),
        ("reversion_only",  _build_reversion_only),
    ]:
        thr_results: dict[str, dict] = {}
        for thr in thresholds:
            stats, curve = run_strategy(bars, factory, enter_threshold=thr)
            stats.name = strat_name
            thr_results[f"thr={thr:.2f}"] = {"stats": stats, "equity_curve": curve}
        result[strat_name] = thr_results

    # combined_sleeves: 50/50 MultiSleeveEngine
    thr_results_combined: dict[str, dict] = {}
    for thr in thresholds:
        stats, curve = run_sleeve_strategy(bars, thr)
        stats.name = "combined_sleeves"
        thr_results_combined[f"thr={thr:.2f}"] = {"stats": stats, "equity_curve": curve}
    result["combined_sleeves"] = thr_results_combined

    return result


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

    # Merge sleeve strategies (trend_only, reversion_only, combined_sleeves)
    sleeve_results = evaluate_sleeves(bars, thresholds)
    strategies_result.update(sleeve_results)

    # Build bars_by_symbol for equal_weight_buyhold benchmark
    bars_by_symbol: dict[str, list[BarEvent]] = {}
    for b in bars:
        key = f"{b.symbol.ticker}[{b.symbol.market.value}]"
        bars_by_symbol.setdefault(key, []).append(b)

    _ewbh_curve, _ewbh_metrics = equal_weight_buyhold(bars_by_symbol)

    return {
        "buy_and_hold": buy_and_hold_return(bars),
        "equal_weight_buyhold": _ewbh_metrics,
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
    lines.append(SURVIVORSHIP_WARNING)
    lines.append("")
    lines.append(_DISCLAIMER)
    lines.append("")

    n_bars = result.get("n_bars", "?")
    thresholds = result.get("thresholds", ())
    bnh = result["buy_and_hold"]
    ewbh = result.get("equal_weight_buyhold", {})

    lines.append(f"  Total bars in dataset : {n_bars}")
    lines.append(f"  Thresholds (fixed grid): {', '.join(f'{t:.2f}' for t in thresholds)}")
    lines.append(f"  Initial capital        : {_INITIAL_KRW:,.0f} KRW")
    lines.append(f"  Cost model             : MarketCostModel (KOSPI 1.41bps+20bps sell tax; NASDAQ 25bps+SEC+TAF)")
    lines.append(f"  FX rate (fixed)        : 1 USD = {_FX_USD_KRW:,.1f} KRW")
    lines.append("")

    # ── Benchmark section ───────────────────────────────────────────────────
    lines.append("  ── BENCHMARKS (gross, no costs; survivorship-biased — same universe) ──")
    lines.append("")
    lines.append("  [1] Buy & Hold — equal-weight average of symbols in the backtest")
    lines.append(f"      Return : {bnh:+.2%}")
    lines.append("")
    if ewbh:
        ewbh_ret = ewbh.get("total_return", 0.0)
        ewbh_n = ewbh.get("n_symbols", "?")
        lines.append(f"  [2] Equal-Weight Buy & Hold — full opportunity set ({ewbh_n} symbols)")
        lines.append(f"      Return : {ewbh_ret:+.2%}")
        lines.append(f"      (Owns all symbols the strategy was allowed to trade.)")
        lines.append("")
    lines.append("  NOTE: To benchmark against a market index (e.g. SPY, KOSPI index),")
    lines.append("  supply an external return series — index data is not fetched here")
    lines.append("  to avoid live network calls and rate-limit issues.")
    lines.append("  See docs/data-limitations.md for guidance.")
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
        "  NOTE: 'Trades' = number of FillEvents received (each buy or sell execution = 1)."
    )
    lines.append(
        "  'Exposure' = fraction of bar-events where the aggregate book holds any nonzero"
    )
    lines.append(
        "    net position.  For single-engine strategies: any nonzero position in the"
    )
    lines.append(
        "    portfolio.  For sleeve strategies (combined_sleeves): union of both sleeve"
    )
    lines.append(
        "    portfolios, checked once per bar — not double-counted.  combined_sleeves"
    )
    lines.append(
        "    exposure is naturally higher because EITHER sleeve being invested triggers it."
    )
    lines.append(
        "  'AvgHold' = average holding period in bars (same definition for all paths):"
    )
    lines.append(
        "    a position opens when net qty goes 0→nonzero, closes when nonzero→0."
    )
    lines.append(
        "    Positions still open at end-of-run count bars held so far (partial hold"
    )
    lines.append(
        "    included).  For sleeve strategies, all sleeve holding periods are pooled."
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
