# tests/test_signal_eval.py
"""Tests for the cross-sectional IC harness — RESEARCH ONLY, no network.

The "teeth" tests prove the harness actually measures predictive power:
a planted predictive signal -> high IC, noise -> ~0, inverted -> negative,
plus a look-ahead guard and the small-cross-section skip/count path.

Synthetic panel: each symbol grows geometrically at a fixed daily drift g_k,
so any trailing-return signal ranks symbols monotonically by g_k, and so does
the forward return — giving a near-perfect (rank) IC by construction.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import math

from trader.core.events import BarEvent, Market, Symbol
from trader.research.signal_eval import evaluate_ic, _rankdata

_START = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _panel(drifts: list[float], n_dates: int, market: Market = Market.NASDAQ) -> dict[str, list[BarEvent]]:
    """Build a synthetic panel. Symbol k grows at fixed daily drift drifts[k]:
    close[d] = 100*prod(1+g) ; open[d] = close[d-1] (gap-free)."""
    ccy = "USD" if market == Market.NASDAQ else "KRW"
    out: dict[str, list[BarEvent]] = {}
    for k, g in enumerate(drifts):
        ticker = f"S{k:03d}"
        sym = Symbol(ticker, market, ccy)
        bars: list[BarEvent] = []
        close = 100.0
        prev_close = 100.0
        for d in range(n_dates):
            ts = _START + timedelta(days=d)
            close = 100.0 * (1.0 + g) ** d
            open_ = prev_close if d > 0 else close
            hi = max(open_, close)
            lo = min(open_, close)
            bars.append(BarEvent(sym, ts, open_, hi, lo, close, 1_000_000))
            prev_close = close
        out[ticker] = bars
    return out


def _trailing_return(n: int):
    def f(hist):
        if len(hist) <= n:
            return None
        return hist[-1].close / hist[-1 - n].close - 1.0
    return f


def _inverted_trailing_return(n: int):
    base = _trailing_return(n)
    def f(hist):
        r = base(hist)
        return None if r is None else -r
    return f


def _noise_signal(hist):
    """Deterministic pseudo-random score from (ticker, date) — decorrelated
    from drift, so average IC over many periods → ~0."""
    last = hist[-1]
    key = f"{last.symbol.ticker}|{last.ts.date().isoformat()}".encode()
    return int(hashlib.md5(key).hexdigest()[:8], 16) / 0xFFFFFFFF


# distinct monotonic drifts: -0.02 .. +0.019 across 40 symbols
_DRIFTS = [0.001 * (k - 20) for k in range(40)]


def test_predictive_signal_high_ic():
    panel = _panel(_DRIFTS, n_dates=80)
    res = evaluate_ic(panel, _trailing_return(10), horizon=5, min_cross_section=30)
    assert res.n_periods >= 8
    assert res.mean_rank_ic > 0.95          # monotonic by construction
    assert res.mean_ic > 0.80
    assert res.ic_t_stat > 3.0              # strongly significant


def test_inverted_signal_negative_ic():
    panel = _panel(_DRIFTS, n_dates=80)
    res = evaluate_ic(panel, _inverted_trailing_return(10), horizon=5, min_cross_section=30)
    assert res.mean_rank_ic < -0.95
    assert res.mean_ic < -0.80
    assert res.ic_t_stat < -3.0


def test_random_signal_near_zero_ic():
    panel = _panel(_DRIFTS, n_dates=120)
    res = evaluate_ic(panel, _noise_signal, horizon=5, min_cross_section=30)
    assert res.n_periods >= 15
    assert abs(res.mean_ic) < 0.25
    assert abs(res.mean_rank_ic) < 0.25
    assert abs(res.ic_t_stat) < 2.0         # not significant


def test_signal_only_sees_history_through_t():
    """Look-ahead guard: signal_fn must never receive a bar dated later than
    the rebalance date, and must never see the final (forward-window) dates."""
    panel = _panel(_DRIFTS, n_dates=60)
    seen: set = set()

    def spy(hist):
        seen.add(hist[-1].ts.date())
        return hist[-1].close  # any valid score

    horizon = 5
    evaluate_ic(panel, spy, horizon=horizon, min_cross_section=30)

    last_rebalance_date = (_START + timedelta(days=60 - horizon - 1)).date()
    very_last_date = (_START + timedelta(days=59)).date()
    assert max(seen) <= last_rebalance_date          # never saw beyond t
    assert very_last_date not in seen                # forward window never seen


def test_small_cross_section_skipped_and_counted():
    panel = _panel(_DRIFTS[:20], n_dates=80)          # only 20 names < min 30
    res = evaluate_ic(panel, _trailing_return(10), horizon=5, min_cross_section=30)
    assert res.n_periods == 0
    assert res.n_skipped_small_xs > 0
    assert math.isnan(res.mean_ic)


def test_nonoverlapping_spacing_defaults_to_horizon():
    panel = _panel(_DRIFTS, n_dates=80)
    res = evaluate_ic(panel, _trailing_return(10), horizon=5, min_cross_section=30)
    assert res.rebalance_spacing == 5                 # defaults to horizon


def test_rankdata_average_ties():
    import numpy as np
    r = _rankdata(np.array([10.0, 30.0, 30.0, 20.0]))
    # sorted: 10(1), 20(2), 30&30 -> avg(3,4)=3.5
    assert list(r) == [1.0, 3.5, 3.5, 2.0]


def test_standard_signals_none_on_short_history():
    from trader.research.signal_eval import momentum_12_1, short_term_reversal
    sym = Symbol("X", Market.NASDAQ, "USD")
    short = [BarEvent(sym, _START + timedelta(days=d), 100, 101, 99, 100.0, 1) for d in range(10)]
    assert momentum_12_1(short) is None            # needs 253 bars
    assert short_term_reversal(short, 5) is not None  # needs only 6
    assert short_term_reversal(short[:3], 5) is None


def test_standard_signals_sign():
    from trader.research.signal_eval import momentum_12_1, short_term_reversal
    sym = Symbol("UP", Market.NASDAQ, "USD")
    # steadily rising series
    up = [BarEvent(sym, _START + timedelta(days=d), 100, 101, 99, 100.0 + d, 1) for d in range(300)]
    assert momentum_12_1(up) > 0                    # rose over 12-1 window
    assert short_term_reversal(up, 5) < 0           # rose recently -> reversal score negative


# ---------------------------------------------------------------------------
# Date-window (split) filtering — rebalance dates only, warmup preserved
# ---------------------------------------------------------------------------

class TestDateWindow:
    def _iso(self, day: int) -> str:
        return (_START + timedelta(days=day)).date().isoformat()

    def test_rebalance_dates_restricted_to_window(self):
        panel = _panel(_DRIFTS, n_dates=120)
        seen: list = []

        def spy(hist):
            seen.append(hist[-1].ts.date())
            return hist[-1].close

        # window = days [40, 80)
        evaluate_ic(panel, spy, horizon=5, min_cross_section=30,
                    date_start=self._iso(40), date_end=self._iso(80))
        lo = (_START + timedelta(days=40)).date()
        hi = (_START + timedelta(days=80)).date()
        assert seen, "should have evaluated some dates"
        assert min(seen) >= lo
        assert max(seen) < hi

    def test_signal_sees_prewindow_warmup(self):
        """A signal needing long warmup still works at the window START because
        the window filters decision dates, not the history the signal sees."""
        panel = _panel(_DRIFTS, n_dates=120)

        def needs_warmup(hist):
            # requires 50 bars of history; would be None if history were truncated
            if len(hist) < 50:
                return None
            return hist[-1].close / hist[-50].close - 1.0

        # window starts at day 55 (only ~5 bars INSIDE window, but 55 of history)
        res = evaluate_ic(panel, needs_warmup, horizon=5, min_cross_section=30,
                          date_start=self._iso(55), date_end=self._iso(110))
        assert res.n_periods >= 5          # signal computed despite short in-window span
        assert res.mean_rank_ic > 0.9      # warmup intact -> still predictive

    def test_strict_split_drops_boundary_crossing(self):
        """With strict_split, a rebalance whose forward window crosses date_end
        is dropped (vs included when strict_split=False)."""
        panel = _panel(_DRIFTS, n_dates=120)
        common = dict(horizon=5, rebalance_spacing=1, min_cross_section=30,
                      date_start=self._iso(40), date_end=self._iso(80))
        strict = evaluate_ic(panel, _trailing_return(10), strict_split=True, **common)
        loose = evaluate_ic(panel, _trailing_return(10), strict_split=False, **common)
        assert loose.n_periods > strict.n_periods   # loose keeps the crossing dates
