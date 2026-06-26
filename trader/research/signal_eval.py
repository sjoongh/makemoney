# trader/research/signal_eval.py
"""RESEARCH ONLY — cross-sectional signal evaluation (Information Coefficient).

Answers the existential question *before* building any strategy:
**does a signal's cross-sectional ranking predict forward returns at all?**

NEVER import from live/paper trading or the backtest/live parity path.

Method (this module, increment 1 — the core IC engine):
  - On each rebalance date ``t`` a ``signal_fn`` receives ONLY the bars with
    ``ts <= t`` (look-ahead is structurally impossible) and returns one score
    per symbol.
  - The forward return is **tradable**: enter at the next bar's OPEN (t+1) and
    exit at the close ``horizon`` trading days later — never the close at ``t``
    (which the signal already used).
  - The cross-sectional Information Coefficient at ``t`` is
    Pearson(scores, forward_returns); rank IC is Spearman.
  - Rebalance dates are spaced ``horizon`` trading days apart by default so the
    IC observations are **non-overlapping** → the naive
    ``t = mean/std*sqrt(n)`` is statistically valid.  (Overlapping rebalances
    with a HAC/Newey-West correction are a later increment.)
  - Dates whose tradable cross-section is smaller than ``min_cross_section``
    are SKIPPED and COUNTED (never silently included).

Deferred to later increments (documented so coverage is explicit):
  quantile spread returns, IC decay curve, US/KR split, cost-adjusted spread,
  PeriodSplit (train/val/holdout) reporting, HAC t-stat for overlapping windows.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from datetime import date as _date, datetime
from typing import Callable, Optional

import numpy as np

from trader.core.events import BarEvent

# A signal sees the point-in-time history (bars with ts <= t, ascending) and
# returns a score, or None when it has insufficient history / no opinion.
SignalFn = Callable[[list[BarEvent]], Optional[float]]


@dataclass
class ICResult:
    """Aggregated cross-sectional IC over the evaluated rebalance dates."""

    horizon: int
    rebalance_spacing: int
    min_cross_section: int

    n_periods: int            # rebalance dates with a usable cross-section
    n_skipped_small_xs: int   # dates skipped: cross-section < min_cross_section
    n_skipped_degenerate: int # dates skipped: zero variance in scores/returns

    mean_ic: float
    std_ic: float
    ic_t_stat: float          # mean/std*sqrt(n) — valid: non-overlapping windows
    ic_ir: float              # mean/std (per-period information ratio of IC)
    mean_rank_ic: float

    ic_series: list[tuple[str, float]]       # (rebalance_date_iso, ic)
    rank_ic_series: list[tuple[str, float]]  # (rebalance_date_iso, rank_ic)

    def summary(self) -> str:
        sig = "—"
        if not math.isnan(self.ic_t_stat):
            sig = "significant" if abs(self.ic_t_stat) >= 2.0 else "NOT significant"
        return (
            f"IC over {self.n_periods} non-overlapping {self.horizon}d periods "
            f"(min_xs={self.min_cross_section}, skipped: "
            f"{self.n_skipped_small_xs} small + {self.n_skipped_degenerate} degenerate)\n"
            f"  mean IC      = {self.mean_ic:+.4f}\n"
            f"  std  IC      = {self.std_ic:.4f}\n"
            f"  IC t-stat    = {self.ic_t_stat:+.2f}  ({sig} at |t|>=2)\n"
            f"  IC IR        = {self.ic_ir:+.3f}\n"
            f"  mean rankIC  = {self.mean_rank_ic:+.4f}"
        )


# ---------------------------------------------------------------------------
# Numeric helpers (numpy only — no scipy dependency)
# ---------------------------------------------------------------------------

def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average ranks (1-based), handling ties like scipy.stats.rankdata."""
    a = np.asarray(a, dtype=float)
    order = a.argsort(kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1, dtype=float)
    # average tied groups
    _, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    if (counts > 1).any():
        sums = np.zeros(len(counts))
        np.add.at(sums, inv, ranks)
        ranks = (sums / counts)[inv]
    return ranks


def _winsorize(a: np.ndarray, pct: float) -> np.ndarray:
    if pct <= 0.0:
        return a
    lo, hi = np.quantile(a, [pct, 1.0 - pct])
    return np.clip(a, lo, hi)


def _pearson(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    if x.std() == 0.0 or y.std() == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------

def evaluate_ic(
    bars_by_symbol: dict[str, list[BarEvent]],
    signal_fn: SignalFn,
    *,
    horizon: int = 21,
    rebalance_spacing: Optional[int] = None,
    min_cross_section: int = 30,
    winsorize_pct: float = 0.0,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    strict_split: bool = True,
) -> ICResult:
    """Compute the cross-sectional Information Coefficient of ``signal_fn``.

    Args:
        bars_by_symbol: symbol -> ascending list of daily BarEvents (adjusted).
        signal_fn:      given the point-in-time history (bars with ts <= t),
                        returns a score or None.  Never receives future bars.
        horizon:        forward-return holding length in trading days
                        (entry = open at t+1, exit = close at t+horizon).
        rebalance_spacing: trading days between rebalance dates.  Defaults to
                        ``horizon`` → non-overlapping, independent IC samples.
        min_cross_section: minimum tradable names at a date to compute IC.
        winsorize_pct:  symmetric tail clip applied to forward returns (e.g.
                        0.01 clips the top/bottom 1%); 0 disables.
        date_start/date_end: restrict REBALANCE DATES to [date_start, date_end)
                        (ISO YYYY-MM-DD).  Only the decision dates ``t`` are
                        filtered — the signal still sees full pre-window warmup
                        history, so split evaluation never zeroes early periods.
        strict_split:   when date_end is set, drop a rebalance whose forward
                        window (exit at t+horizon) crosses date_end, so a train
                        score never uses validation-period realized returns
                        (split-disciplined selection).  Default True.

    Returns:
        ICResult.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    spacing = rebalance_spacing if rebalance_spacing is not None else horizon
    if spacing < 1:
        raise ValueError("rebalance_spacing must be >= 1")
    d_start = datetime.strptime(date_start, "%Y-%m-%d").date() if date_start else None
    d_end = datetime.strptime(date_end, "%Y-%m-%d").date() if date_end else None

    # Per-symbol: ascending bars, the date list (for bisect), and a date->bar map.
    sym_bars: dict[str, list[BarEvent]] = {}
    sym_dates: dict[str, list[_date]] = {}
    sym_map: dict[str, dict[_date, BarEvent]] = {}
    all_dates: set[_date] = set()
    for sym, bars in bars_by_symbol.items():
        if not bars:
            continue
        sb = sorted(bars, key=lambda b: b.ts)
        ds = [b.ts.date() for b in sb]
        sym_bars[sym] = sb
        sym_dates[sym] = ds
        sym_map[sym] = {b.ts.date(): b for b in sb}
        all_dates.update(ds)

    union = sorted(all_dates)
    ic_series: list[tuple[str, float]] = []
    rank_series: list[tuple[str, float]] = []
    n_small = 0
    n_degen = 0

    # Rebalance at union[i]; need entry at i+1 and exit at i+horizon.
    # Restrict decision dates to [d_start, d_end) — but keep stepping aligned to
    # the first in-window index so spacing stays non-overlapping within the window.
    i = bisect.bisect_left(union, d_start) if d_start is not None else 0
    last_valid = len(union) - horizon - 1  # need i+horizon <= len-1
    while i <= last_valid:
        t = union[i]
        if d_end is not None and t >= d_end:
            break  # union is sorted — all later dates are out of window too
        entry_date = union[i + 1]
        exit_date = union[i + horizon]

        # split-discipline: don't let a train forward-window peek into validation
        if strict_split and d_end is not None and exit_date >= d_end:
            i += spacing
            continue

        scores: list[float] = []
        fwds: list[float] = []
        for sym, ds in sym_dates.items():
            # history with ts <= t  (look-ahead impossible: future bars excluded)
            cutoff = bisect.bisect_right(ds, t)
            if cutoff == 0:
                continue
            score = signal_fn(sym_bars[sym][:cutoff])
            if score is None or (isinstance(score, float) and math.isnan(score)):
                continue
            entry = sym_map[sym].get(entry_date)
            exit_ = sym_map[sym].get(exit_date)
            if entry is None or exit_ is None or entry.open <= 0:
                continue
            fwds.append(exit_.close / entry.open - 1.0)
            scores.append(float(score))

        if len(scores) < min_cross_section:
            n_small += 1
            i += spacing
            continue

        s = np.asarray(scores, dtype=float)
        f = _winsorize(np.asarray(fwds, dtype=float), winsorize_pct)

        ic = _pearson(s, f)
        ric = _pearson(_rankdata(s), _rankdata(f))
        if ic is None or ric is None:
            n_degen += 1
            i += spacing
            continue

        iso = t.isoformat()
        ic_series.append((iso, ic))
        rank_series.append((iso, ric))
        i += spacing

    n = len(ic_series)
    ic_vals = np.asarray([v for _, v in ic_series], dtype=float)
    ric_vals = np.asarray([v for _, v in rank_series], dtype=float)

    if n == 0:
        mean_ic = std_ic = t_stat = ic_ir = mean_ric = float("nan")
    else:
        mean_ic = float(ic_vals.mean())
        mean_ric = float(ric_vals.mean())
        if n >= 2:
            std_ic = float(ic_vals.std(ddof=1))
            if std_ic > 0:
                t_stat = mean_ic / std_ic * math.sqrt(n)
                ic_ir = mean_ic / std_ic
            else:
                t_stat = float("nan")
                ic_ir = float("nan")
        else:
            std_ic = float("nan")
            t_stat = float("nan")
            ic_ir = float("nan")

    return ICResult(
        horizon=horizon,
        rebalance_spacing=spacing,
        min_cross_section=min_cross_section,
        n_periods=n,
        n_skipped_small_xs=n_small,
        n_skipped_degenerate=n_degen,
        mean_ic=mean_ic,
        std_ic=std_ic,
        ic_t_stat=t_stat,
        ic_ir=ic_ir,
        mean_rank_ic=mean_ric,
        ic_series=ic_series,
        rank_ic_series=rank_series,
    )


# ---------------------------------------------------------------------------
# Standard candidate signals (point-in-time; return None on short history)
# ---------------------------------------------------------------------------

def momentum_12_1(hist: list[BarEvent]) -> Optional[float]:
    """Classic 12-1 momentum: 12-month return skipping the most recent month.

    close[t-21] / close[t-252] - 1.  Needs >= 253 bars.
    """
    if len(hist) < 253:
        return None
    return hist[-22].close / hist[-253].close - 1.0


def short_term_reversal(hist: list[BarEvent], lookback: int = 5) -> Optional[float]:
    """Short-term reversal: NEGATIVE of the last ``lookback``-day return.

    A positive score = recently fell = expected to bounce.  Needs lookback+1 bars.
    """
    if len(hist) < lookback + 1:
        return None
    return -(hist[-1].close / hist[-1 - lookback].close - 1.0)


def momentum_6_1(hist: list[BarEvent]) -> Optional[float]:
    """6-1 momentum: close[t-21]/close[t-126]-1.  Needs >= 127 bars."""
    if len(hist) < 127:
        return None
    return hist[-22].close / hist[-127].close - 1.0


def momentum_3_1(hist: list[BarEvent]) -> Optional[float]:
    """3-1 momentum: close[t-21]/close[t-63]-1.  Needs >= 64 bars."""
    if len(hist) < 64:
        return None
    return hist[-22].close / hist[-64].close - 1.0


def low_volatility(hist: list[BarEvent], lookback: int = 60) -> Optional[float]:
    """Low-volatility anomaly: NEGATIVE realized vol of the last ``lookback``
    daily returns (higher score = lower vol = expected higher risk-adj return).
    Needs lookback+1 bars."""
    if len(hist) < lookback + 1:
        return None
    closes = [b.close for b in hist[-(lookback + 1):]]
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    arr = np.asarray(rets, dtype=float)
    if arr.std() == 0.0:
        return 0.0
    return -float(arr.std(ddof=1))
