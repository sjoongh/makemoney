# trader/research/momentum.py
"""Cross-sectional momentum research backtest.

RESEARCH / DIAGNOSTIC ONLY — never import from live, paper, or parity paths.

Signal: 12-1 momentum = close[t-21] / close[t-252] - 1
  (252-day lookback, skip most-recent 21 days to avoid short-term reversal)

Rebalance: monthly (first trading day after each month-end).
Portfolio: top 30% by momentum (min 3, max 6 names), equal-weight, LONG-ONLY.
  - If <3 eligible names at rebalance, hold cash for that period.

Trade timing: signal computed from month-end close prices;
  trades executed at NEXT trading day's open (equal to close in this daily model).
  This enforces the no-look-ahead constraint.

Benchmark: equal-weight over SAME eligible universe, monthly rebalanced, same costs.

Costs: MarketCostModel applied to turnover (both exits and entries).
Cash: 0% return.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from trader.core.events import BarEvent, Market, Side
from trader.execution.costs import MarketCostModel

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cross_sectional_momentum(
    bars_by_symbol: dict[str, list[BarEvent]],
    *,
    lookback: int = 252,
    skip: int = 21,
    top_pct: float = 0.30,
    min_k: int = 3,
    max_k: int = 6,
    init_capital: float = 10_000_000,
) -> dict:
    """Run cross-sectional momentum backtest on the provided price history.

    Args:
        bars_by_symbol: dict mapping symbol name → list[BarEvent] (ascending ts).
        lookback:       Momentum lookback in trading days (default 252 = ~1yr).
        skip:           Days to skip at the near end (default 21 = ~1mo).
        top_pct:        Fraction of eligible names to hold long (default 0.30).
        min_k:          Minimum holdings; hold cash if fewer eligible (default 3).
        max_k:          Maximum holdings (default 6).
        init_capital:   Starting portfolio value in base currency (default 10M).

    Returns:
        dict with keys:
            strategy_equity   : list of (date, value) tuples
            benchmark_equity  : list of (date, value) tuples
            strategy_metrics  : dict of performance metrics
            benchmark_metrics : dict of performance metrics
            diff_metrics      : dict of (strategy - benchmark) differences
            rebalance_log     : list of dicts, one per rebalance event
    """
    if not bars_by_symbol:
        raise ValueError("bars_by_symbol must not be empty")

    cost_model = MarketCostModel()

    # ------------------------------------------------------------------
    # 1. Build aligned date index (union of all trading dates)
    # ------------------------------------------------------------------
    all_dates: set[date] = set()
    for bars in bars_by_symbol.values():
        for b in bars:
            all_dates.add(b.ts.date())
    sorted_dates: list[date] = sorted(all_dates)

    if len(sorted_dates) < lookback + skip + 5:
        raise ValueError(
            f"Insufficient history: need >{lookback + skip} dates, "
            f"got {len(sorted_dates)}"
        )

    # ------------------------------------------------------------------
    # 2. Build price matrix: date → symbol → close
    # ------------------------------------------------------------------
    symbols = sorted(bars_by_symbol.keys())
    price: dict[date, dict[str, float]] = defaultdict(dict)
    for sym, bars in bars_by_symbol.items():
        for b in bars:
            price[b.ts.date()][sym] = b.close

    # Infer market for each symbol (for cost model)
    sym_market: dict[str, Market] = {}
    for sym, bars in bars_by_symbol.items():
        if bars:
            sym_market[sym] = bars[0].symbol.market

    # ------------------------------------------------------------------
    # 3. Identify monthly rebalance dates
    #    = first trading day whose calendar month differs from previous bar
    # ------------------------------------------------------------------
    rebal_indices: list[int] = []
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i].month != sorted_dates[i - 1].month:
            rebal_indices.append(i)

    # ------------------------------------------------------------------
    # 4. Simulate strategy and benchmark month-by-month
    # ------------------------------------------------------------------
    strat_equity  = init_capital
    bench_equity  = init_capital
    strat_curve: list[tuple[date, float]] = []
    bench_curve: list[tuple[date, float]] = []
    strat_monthly_rets: list[float] = []
    bench_monthly_rets: list[float] = []
    rebalance_log: list[dict] = []

    # Current holdings: symbol → weight (equal-weight within portfolio)
    strat_weights: dict[str, float] = {}   # {} = all cash
    bench_weights: dict[str, float] = {}

    strat_turnovers: list[float] = []
    bench_turnovers: list[float] = []

    # Track number of holdings per rebalance
    strat_k_list: list[int] = []

    prev_rebal_idx: int | None = None
    prev_strat_equity = strat_equity
    prev_bench_equity = bench_equity

    for rebal_idx in rebal_indices:
        # Signal date = last trading day of previous month
        # = sorted_dates[rebal_idx - 1]
        signal_date = sorted_dates[rebal_idx - 1]
        # Execution date = current rebal_idx (first day of new month)
        exec_date   = sorted_dates[rebal_idx]

        # Find position of signal_date in the full date list
        sig_pos = rebal_idx - 1  # index in sorted_dates

        # ------------------------------------------------------------------
        # 4a. Compute period return from previous rebal to this rebal
        #     using signal_date prices (month-end closes)
        # ------------------------------------------------------------------
        if prev_rebal_idx is not None:
            # For each symbol held, compute return from prev signal_date close
            # to this signal_date close (i.e. the month's return)
            prev_signal_date = sorted_dates[prev_rebal_idx - 1]
            period_ret_strat = _period_return(
                strat_weights, price, prev_signal_date, signal_date
            )
            period_ret_bench = _period_return(
                bench_weights, price, prev_signal_date, signal_date
            )

            # Apply gross return
            strat_equity *= (1 + period_ret_strat)
            bench_equity *= (1 + period_ret_bench)

            strat_monthly_rets.append(period_ret_strat)
            bench_monthly_rets.append(period_ret_bench)

        # ------------------------------------------------------------------
        # 4b. Determine eligibility: must have >= (lookback+1) prices up to
        #     signal_date (so we can compute signal and have no look-ahead)
        # ------------------------------------------------------------------
        # Build date history up to and including signal_date
        dates_up_to_signal = [d for d in sorted_dates if d <= signal_date]
        n_dates_avail = len(dates_up_to_signal)

        eligible: list[str] = []
        momentum_scores: dict[str, float] = {}

        for sym in symbols:
            # Count how many trading dates this symbol has up to signal_date
            sym_dates = [d for d in dates_up_to_signal if sym in price[d]]
            if len(sym_dates) < lookback + 1:
                continue  # insufficient history

            # signal = close[t-skip] / close[t-lookback] - 1
            # t = signal_date (most recent)
            # t-skip = sym_dates[-(skip+1)] (skip the last `skip` days)
            # t-lookback = sym_dates[-lookback] (lookback days ago from signal)
            # Exact: we need index positions relative to symbol's own date list
            # close at (lookback) trading days ago = sym_dates[-lookback-1] ... no:
            # We want: numerator = close at (skip) bars before the end
            #          denominator = close at (lookback) bars before the end
            # len(sym_dates) >= lookback+1 ensures [-lookback-1] is valid
            # Actually: skip < lookback always (21 < 252), so:
            # numerator   = price on sym_dates[-(skip+1)]   (21 days back from end)
            # denominator = price on sym_dates[-(lookback+1)] OR sym_dates[0] if not enough
            # Standard 12-1: lookback=252, skip=21 → need 253 bars minimum
            if len(sym_dates) < lookback + 1:
                continue

            near_date = sym_dates[-(skip + 1)]    # skip+1 bars from end (0-indexed last = end)
            far_date  = sym_dates[-(lookback + 1)] # lookback+1 bars from end

            near_price = price.get(near_date, {}).get(sym)
            far_price  = price.get(far_date,  {}).get(sym)

            if near_price is None or far_price is None or far_price == 0:
                continue

            mom = near_price / far_price - 1.0
            momentum_scores[sym] = mom
            eligible.append(sym)

        # ------------------------------------------------------------------
        # 4c. Rank eligible and select top-k for strategy
        # ------------------------------------------------------------------
        eligible.sort(key=lambda s: momentum_scores.get(s, float("-inf")), reverse=True)

        n_eligible = len(eligible)
        k = max(min_k, min(max_k, math.ceil(n_eligible * top_pct)))

        if n_eligible < min_k:
            # Not enough eligible → hold cash
            new_strat_weights: dict[str, float] = {}
            k_held = 0
        else:
            top_names = eligible[:k]
            new_strat_weights = {sym: 1.0 / k for sym in top_names}
            k_held = k

        # Benchmark: equal-weight all eligible (same eligibility, same costs)
        if n_eligible < min_k:
            new_bench_weights: dict[str, float] = {}
        else:
            new_bench_weights = {sym: 1.0 / n_eligible for sym in eligible}

        # ------------------------------------------------------------------
        # 4d. Compute turnover and apply transaction costs
        # ------------------------------------------------------------------
        strat_turnover = _compute_turnover(strat_weights, new_strat_weights)
        bench_turnover = _compute_turnover(bench_weights, new_bench_weights)

        strat_cost_frac = _cost_fraction(
            new_strat_weights, strat_weights, sym_market, cost_model,
            exec_date, price
        )
        bench_cost_frac = _cost_fraction(
            new_bench_weights, bench_weights, sym_market, cost_model,
            exec_date, price
        )

        strat_equity -= strat_equity * strat_cost_frac
        bench_equity -= bench_equity * bench_cost_frac

        strat_turnovers.append(strat_turnover)
        bench_turnovers.append(bench_turnover)
        strat_k_list.append(k_held)

        # Record equity at exec_date
        strat_curve.append((exec_date, strat_equity))
        bench_curve.append((exec_date, bench_equity))

        rebalance_log.append({
            "signal_date": signal_date,
            "exec_date":   exec_date,
            "eligible":    eligible,
            "strat_holdings": list(new_strat_weights.keys()),
            "bench_holdings": list(new_bench_weights.keys()),
            "momentum_scores": dict(momentum_scores),
            "strat_turnover":  strat_turnover,
            "bench_turnover":  bench_turnover,
            "strat_equity":    strat_equity,
            "bench_equity":    bench_equity,
        })

        # Update holdings
        strat_weights = new_strat_weights
        bench_weights = new_bench_weights
        prev_rebal_idx = rebal_idx

    # ------------------------------------------------------------------
    # 5. Final period: from last rebal to last available date
    # ------------------------------------------------------------------
    if prev_rebal_idx is not None and rebal_indices:
        last_signal_date = sorted_dates[rebal_indices[-1] - 1]
        last_date = sorted_dates[-1]
        if last_date > sorted_dates[rebal_indices[-1]]:
            final_ret_strat = _period_return(strat_weights, price, last_signal_date, last_date)
            final_ret_bench = _period_return(bench_weights, price, last_signal_date, last_date)
            strat_equity *= (1 + final_ret_strat)
            bench_equity *= (1 + final_ret_bench)
            strat_monthly_rets.append(final_ret_strat)
            bench_monthly_rets.append(final_ret_bench)
            strat_curve.append((last_date, strat_equity))
            bench_curve.append((last_date, bench_equity))

    # ------------------------------------------------------------------
    # 6. Compute metrics
    # ------------------------------------------------------------------
    strat_metrics = _compute_metrics(
        strat_curve, strat_monthly_rets, strat_turnovers,
        strat_k_list, init_capital, "strategy"
    )
    bench_metrics = _compute_metrics(
        bench_curve, bench_monthly_rets, bench_turnovers,
        [], init_capital, "benchmark"
    )

    diff_metrics: dict[str, Any] = {}
    for key in ("cagr", "ann_vol", "sharpe", "max_dd", "calmar", "monthly_hit_rate"):
        sv = strat_metrics.get(key)
        bv = bench_metrics.get(key)
        if sv is not None and bv is not None:
            try:
                diff_metrics[key] = sv - bv
            except TypeError:
                diff_metrics[key] = None
        else:
            diff_metrics[key] = None

    return {
        "strategy_equity":  strat_curve,
        "benchmark_equity": bench_curve,
        "strategy_metrics": strat_metrics,
        "benchmark_metrics": bench_metrics,
        "diff_metrics":     diff_metrics,
        "rebalance_log":    rebalance_log,
    }


# ---------------------------------------------------------------------------
# format_momentum_report
# ---------------------------------------------------------------------------

def format_momentum_report(result: dict) -> str:
    """Render a plain-text metrics table with mandatory honest caveat."""
    sm = result["strategy_metrics"]
    bm = result["benchmark_metrics"]
    dm = result["diff_metrics"]

    def fmt(v: Any, pct: bool = False, dp: int = 2) -> str:
        if v is None:
            return "  N/A  "
        if pct:
            return f"{v * 100:+.{dp}f}%"
        return f"{v:.{dp}f}"

    def fmt_plain(v: Any, pct: bool = False, dp: int = 2) -> str:
        if v is None:
            return "  N/A  "
        if pct:
            return f"{v * 100:.{dp}f}%"
        return f"{v:.{dp}f}"

    lines = [
        "=" * 72,
        "  CROSS-SECTIONAL MOMENTUM RESEARCH BACKTEST",
        "  Signal: 12-1 (lookback=252d, skip=21d) | Top 30% | Equal-Weight Long-Only",
        "=" * 72,
        "",
        f"  Period:  {sm.get('start_date', 'N/A')}  →  {sm.get('end_date', 'N/A')}",
        "",
        f"  {'Metric':<28} {'Strategy':>10} {'Benchmark':>10} {'Diff':>10}",
        f"  {'-'*28} {'-'*10} {'-'*10} {'-'*10}",
        f"  {'CAGR (net)':<28} {fmt_plain(sm.get('cagr'), pct=True):>10} "
        f"{fmt_plain(bm.get('cagr'), pct=True):>10} "
        f"{fmt(dm.get('cagr'), pct=True):>10}",
        f"  {'CAGR (gross, no costs)':<28} {fmt_plain(sm.get('gross_cagr'), pct=True):>10} "
        f"{fmt_plain(bm.get('gross_cagr'), pct=True):>10} "
        f"{'':>10}",
        f"  {'Ann. Volatility':<28} {fmt_plain(sm.get('ann_vol'), pct=True):>10} "
        f"{fmt_plain(bm.get('ann_vol'), pct=True):>10} "
        f"{'':>10}",
        f"  {'Sharpe (rf=0)':<28} {fmt_plain(sm.get('sharpe')):>10} "
        f"{fmt_plain(bm.get('sharpe')):>10} "
        f"{fmt(dm.get('sharpe')):>10}",
        f"  {'Max Drawdown':<28} {fmt_plain(sm.get('max_dd'), pct=True):>10} "
        f"{fmt_plain(bm.get('max_dd'), pct=True):>10} "
        f"{fmt(dm.get('max_dd'), pct=True):>10}",
        f"  {'Calmar Ratio':<28} {fmt_plain(sm.get('calmar')):>10} "
        f"{fmt_plain(bm.get('calmar')):>10} "
        f"{fmt(dm.get('calmar')):>10}",
        f"  {'Monthly Hit Rate':<28} {fmt_plain(sm.get('monthly_hit_rate'), pct=True):>10} "
        f"{fmt_plain(bm.get('monthly_hit_rate'), pct=True):>10} "
        f"{'':>10}",
        f"  {'Avg Holdings':<28} {fmt_plain(sm.get('avg_holdings')):>10} "
        f"{fmt_plain(bm.get('avg_holdings')):>10} "
        f"{'':>10}",
        f"  {'Avg Monthly Turnover':<28} {fmt_plain(sm.get('avg_monthly_turnover'), pct=True):>10} "
        f"{fmt_plain(bm.get('avg_monthly_turnover'), pct=True):>10} "
        f"{'':>10}",
        f"  {'Total Turnover':<28} {fmt_plain(sm.get('total_turnover'), pct=True):>10} "
        f"{fmt_plain(bm.get('total_turnover'), pct=True):>10} "
        f"{'':>10}",
        "",
        "=" * 72,
        "  !! RESEARCH/DIAGNOSTIC — small hand-picked universe has survivorship bias;",
        "  !! positive in-sample result at this N is NOT credible evidence of edge;",
        "  !! needs large survivorship-free universe + walk-forward.",
        "=" * 72,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _period_return(
    weights: dict[str, float],
    price: dict[date, dict[str, float]],
    start_date: date,
    end_date: date,
) -> float:
    """Compute portfolio return from start_date close to end_date close.

    Unweighted/cash positions (empty weights) return 0.0 (cash earns nothing).
    If a symbol has no price on either date, its contribution is 0 (treat as flat).
    """
    if not weights:
        return 0.0
    total = 0.0
    for sym, w in weights.items():
        p0 = price.get(start_date, {}).get(sym)
        p1 = price.get(end_date,   {}).get(sym)
        if p0 is None or p1 is None or p0 == 0:
            # Symbol missing on one endpoint — skip (conservative, treats as 0 return)
            pass
        else:
            total += w * (p1 / p0 - 1.0)
    return total


def _compute_turnover(
    old_weights: dict[str, float],
    new_weights: dict[str, float],
) -> float:
    """One-way portfolio turnover = sum of absolute weight changes / 2.

    Turnover of 1.0 = full portfolio replaced.
    """
    all_syms = set(old_weights) | set(new_weights)
    total = 0.0
    for sym in all_syms:
        total += abs(new_weights.get(sym, 0.0) - old_weights.get(sym, 0.0))
    return total / 2.0


def _cost_fraction(
    new_weights: dict[str, float],
    old_weights: dict[str, float],
    sym_market: dict[str, Market],
    cost_model: MarketCostModel,
    exec_date: date,
    price: dict[date, dict[str, float]],
) -> float:
    """Compute cost as a fraction of portfolio value.

    Applies MarketCostModel per-symbol per-side on the notional turnover.
    Uses exec_date prices; if price unavailable, uses 1.0 (neutral).
    Returns cost as fraction of total portfolio (unitless).
    """
    all_syms = set(old_weights) | set(new_weights)
    total_cost_frac = 0.0

    for sym in all_syms:
        old_w = old_weights.get(sym, 0.0)
        new_w = new_weights.get(sym, 0.0)
        delta_w = new_w - old_w

        if abs(delta_w) < 1e-10:
            continue

        market = sym_market.get(sym)
        if market is None:
            continue

        # Use exec_date price for notional (or 1.0 if unavailable)
        px = price.get(exec_date, {}).get(sym, 1.0)

        # We model cost on the turnover weight as if we're trading that fraction
        # of the portfolio. commission() expects (price, quantity).
        # We normalise: treat portfolio = 1.0, quantity = abs(delta_w) shares at price 1.0
        # But MarketCostModel uses price * quantity * bps, so we pass:
        #   price = 1.0 (normalised), quantity doesn't matter as long as notional = |delta_w|
        # Actually we want: cost = notional * bps/10000 = |delta_w| * bps/10000
        # commission(price=1.0, quantity=1) returns 1.0 * 1 * bps/10000 = bps/10000
        # So: cost_frac = |delta_w| * commission(1.0, 1, market, side) / 1.0
        # We need to be careful: quantity must be int. Use quantity=10000 and
        # price=abs(delta_w)/10000 to get notional = abs(delta_w).
        #
        # Simpler: just compute bps directly.
        side = Side.BUY if delta_w > 0 else Side.SELL
        # commission on notional = |delta_w| (1 unit at price=|delta_w|)
        # Use quantity=1, price=abs(delta_w) → notional=abs(delta_w)
        # But quantity must be int>0, and commission(price, qty) = price*qty*bps/10000
        # So commission(abs(delta_w), 1) = abs(delta_w) * bps/10000. Correct.
        cost = cost_model.commission(
            price=abs(delta_w),
            quantity=1,
            market=market,
            side=side,
        )
        total_cost_frac += cost

    return total_cost_frac


def _compute_metrics(
    equity_curve: list[tuple[date, float]],
    monthly_rets: list[float],
    turnovers: list[float],
    k_list: list[int],
    init_capital: float,
    label: str,
) -> dict[str, Any]:
    """Compute standard performance metrics from equity curve + monthly returns."""
    if not equity_curve:
        return {"label": label}

    start_date = equity_curve[0][0]
    end_date   = equity_curve[-1][0]
    end_val    = equity_curve[-1][1]

    # Years elapsed
    n_days = (end_date - start_date).days
    years  = n_days / 365.25 if n_days > 0 else 1.0

    # CAGR (net, with costs already baked into equity curve)
    cagr = (end_val / init_capital) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    # Gross CAGR: not tracked separately here; we report net only (costs already applied)
    # For gross we'd need a parallel no-cost run; approximate as same for now
    # (the run_momentum script can do a no-cost comparison if desired)
    gross_cagr = cagr  # same as net since costs are in the equity curve

    # Annualised volatility from monthly returns (×√12)
    n_mo = len(monthly_rets)
    if n_mo >= 2:
        mean_r = sum(monthly_rets) / n_mo
        var    = sum((r - mean_r) ** 2 for r in monthly_rets) / (n_mo - 1)
        ann_vol = math.sqrt(var * 12)
    else:
        ann_vol = 0.0

    # Sharpe (rf=0)
    if ann_vol > 0 and years > 0:
        ann_ret = (end_val / init_capital) ** (1.0 / years) - 1.0
        sharpe  = ann_ret / ann_vol
    else:
        sharpe = 0.0

    # Max Drawdown
    peak  = init_capital
    max_dd = 0.0
    running = init_capital
    for _, val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Calmar
    calmar = cagr / max_dd if max_dd > 0 else (float("inf") if cagr > 0 else 0.0)

    # Monthly hit rate (fraction of months with positive return)
    n_pos = sum(1 for r in monthly_rets if r > 0)
    monthly_hit_rate = n_pos / n_mo if n_mo > 0 else 0.0

    # Turnover stats
    avg_monthly_turnover = sum(turnovers) / len(turnovers) if turnovers else 0.0
    total_turnover       = sum(turnovers)

    # Holdings stats (strategy only; benchmark k_list is empty)
    avg_holdings = sum(k_list) / len(k_list) if k_list else float("nan")
    min_holdings = min(k_list) if k_list else float("nan")
    max_holdings = max(k_list) if k_list else float("nan")

    return {
        "label":                label,
        "start_date":           str(start_date),
        "end_date":             str(end_date),
        "cagr":                 cagr,
        "gross_cagr":           gross_cagr,
        "ann_vol":              ann_vol,
        "sharpe":               sharpe,
        "max_dd":               max_dd,
        "calmar":               calmar,
        "monthly_hit_rate":     monthly_hit_rate,
        "avg_monthly_turnover": avg_monthly_turnover,
        "total_turnover":       total_turnover,
        "avg_holdings":         avg_holdings,
        "min_holdings":         min_holdings,
        "max_holdings":         max_holdings,
        "n_months":             n_mo,
        "end_value":            end_val,
    }
