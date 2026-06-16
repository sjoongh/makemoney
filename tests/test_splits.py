# tests/test_splits.py
"""Tests for trader/research/splits.py (P1 chronological split discipline)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from trader.core.events import BarEvent, Market, Symbol
from trader.research.splits import (
    PeriodSplit,
    chronological_split,
    filter_bars_to_window,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bars(
    start_date: str,
    n_days: int,
    ticker: str = "AAPL",
) -> list[BarEvent]:
    """Create n daily bars starting at start_date."""
    sym = Symbol(ticker, Market.NASDAQ, "USD")
    t0  = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    return [
        BarEvent(sym, t0 + timedelta(days=i), 100.0, 101.0, 99.0, 100.0, 1000)
        for i in range(n_days)
    ]


# ---------------------------------------------------------------------------
# chronological_split — basic correctness
# ---------------------------------------------------------------------------

class TestChronologicalSplit:
    def test_returns_period_split(self):
        sp = chronological_split("2015-01-01", "2024-12-31")
        assert isinstance(sp, PeriodSplit)

    def test_train_start_matches_input_start(self):
        sp = chronological_split("2015-01-01", "2024-12-31")
        assert sp.train_start == "2015-01-01"

    def test_holdout_end_matches_input_end(self):
        sp = chronological_split("2015-01-01", "2024-12-31")
        assert sp.holdout_end == "2024-12-31"

    def test_contiguous_no_gaps(self):
        sp = chronological_split("2015-01-01", "2024-12-31")
        # train end == validation start
        assert sp.train_end == sp.validation_start
        # validation end == holdout start
        assert sp.validation_end == sp.holdout_start

    def test_chronological_order(self):
        sp = chronological_split("2015-01-01", "2024-12-31")
        assert sp.train_start < sp.train_end
        assert sp.train_end <= sp.validation_start
        assert sp.validation_start < sp.validation_end
        assert sp.validation_end <= sp.holdout_start
        assert sp.holdout_start < sp.holdout_end

    def test_holdout_is_most_recent(self):
        """Holdout must be the most recent (latest) slice."""
        sp = chronological_split("2015-01-01", "2024-12-31")
        assert sp.holdout_start > sp.validation_start
        assert sp.holdout_start >= sp.validation_end

    def test_custom_fractions(self):
        sp = chronological_split(
            "2015-01-01", "2024-12-31",
            train=0.6, validation=0.2, holdout=0.2
        )
        from datetime import date
        d_start = date.fromisoformat("2015-01-01")
        d_end   = date.fromisoformat("2024-12-31")
        total   = (d_end - d_start).days

        train_days = (date.fromisoformat(sp.train_end) - d_start).days
        val_days   = (date.fromisoformat(sp.validation_end) - date.fromisoformat(sp.validation_start)).days
        hold_days  = (d_end - date.fromisoformat(sp.holdout_start)).days

        # Fractions should be approximately correct (within 2 days rounding)
        assert abs(train_days / total - 0.6) < 0.02
        assert abs(val_days   / total - 0.2) < 0.02

    def test_default_fractions_roughly_50_25_25(self):
        sp = chronological_split("2010-01-01", "2020-01-01")
        from datetime import date
        d_start = date.fromisoformat("2010-01-01")
        d_end   = date.fromisoformat("2020-01-01")
        total   = (d_end - d_start).days

        train_days = (date.fromisoformat(sp.train_end) - d_start).days
        # Within 2% of 50%
        assert abs(train_days / total - 0.5) < 0.02

    def test_fractions_must_sum_to_one(self):
        with pytest.raises(ValueError, match="sum to 1"):
            chronological_split("2015-01-01", "2020-01-01", train=0.5, validation=0.3, holdout=0.3)

    def test_end_before_start_raises(self):
        with pytest.raises(ValueError):
            chronological_split("2020-01-01", "2015-01-01")

    def test_equal_start_end_raises(self):
        with pytest.raises(ValueError):
            chronological_split("2020-01-01", "2020-01-01")

    def test_zero_fraction_raises(self):
        with pytest.raises(ValueError):
            chronological_split("2015-01-01", "2020-01-01", train=0.0, validation=0.5, holdout=0.5)

    def test_range_too_short_raises(self):
        # 3-day range cannot make 3 non-trivial splits
        with pytest.raises(ValueError):
            chronological_split("2020-01-01", "2020-01-04")

    def test_frozen(self):
        sp = chronological_split("2015-01-01", "2024-12-31")
        with pytest.raises((AttributeError, TypeError)):
            sp.train = ("x", "y")  # type: ignore[misc]

    def test_summary_contains_holdout_warning(self):
        sp = chronological_split("2015-01-01", "2024-12-31")
        summary = sp.summary()
        assert "holdout" in summary.lower()
        assert "ONCE" in summary or "DO NOT" in summary or "once" in summary.lower()

    def test_non_overlapping_three_windows(self):
        """No date can appear in two windows simultaneously."""
        sp = chronological_split("2015-01-01", "2020-12-31")
        from datetime import date, timedelta as td
        d = date.fromisoformat("2015-01-01")
        d_end = date.fromisoformat("2020-12-31")

        t_start = date.fromisoformat(sp.train_start)
        t_end   = date.fromisoformat(sp.train_end)
        v_start = date.fromisoformat(sp.validation_start)
        v_end   = date.fromisoformat(sp.validation_end)
        h_start = date.fromisoformat(sp.holdout_start)
        h_end   = date.fromisoformat(sp.holdout_end)

        # Boundaries: train=[t_start,t_end), val=[v_start,v_end), holdout=[h_start,h_end+1)
        assert t_end == v_start   # contiguous, no gap
        assert v_end == h_start   # contiguous, no gap
        # No overlap since splits are half-open
        assert t_end <= v_start
        assert v_end <= h_start


# ---------------------------------------------------------------------------
# filter_bars_to_window
# ---------------------------------------------------------------------------

class TestFilterBarsToWindow:
    def test_empty_bars_returns_empty(self):
        assert filter_bars_to_window([], "2020-01-01", "2021-01-01") == []

    def test_all_bars_in_window(self):
        bars = _make_bars("2020-01-01", 10)
        result = filter_bars_to_window(bars, "2020-01-01", "2021-01-01")
        assert len(result) == 10

    def test_start_inclusive(self):
        """Bar exactly on start_date must be included."""
        bars = _make_bars("2020-01-01", 5)
        result = filter_bars_to_window(bars, "2020-01-01", "2020-12-31")
        # First bar is 2020-01-01 — must be in result
        first_dates = [b.ts.date().isoformat() for b in result]
        assert "2020-01-01" in first_dates

    def test_end_exclusive(self):
        """Bar exactly on end_date must NOT be included."""
        bars = _make_bars("2020-01-01", 5)
        # Last bar is 2020-01-05 (0-indexed day 4)
        # Set end = 2020-01-05 → last bar excluded
        result = filter_bars_to_window(bars, "2020-01-01", "2020-01-05")
        dates = [b.ts.date().isoformat() for b in result]
        assert "2020-01-05" not in dates
        assert "2020-01-01" in dates
        assert len(result) == 4  # days 1,2,3,4 (0-indexed)

    def test_no_bars_in_window(self):
        bars = _make_bars("2020-01-01", 10)
        result = filter_bars_to_window(bars, "2022-01-01", "2023-01-01")
        assert result == []

    def test_partial_overlap(self):
        bars = _make_bars("2020-01-01", 20)  # 2020-01-01 to 2020-01-20
        # Window: 2020-01-05 to 2020-01-15 (exclusive)
        result = filter_bars_to_window(bars, "2020-01-05", "2020-01-15")
        dates = [b.ts.date().isoformat() for b in result]
        assert "2020-01-05" in dates      # inclusive start
        assert "2020-01-15" not in dates  # exclusive end
        assert "2020-01-14" in dates
        assert len(result) == 10          # 5,6,7,8,9,10,11,12,13,14 = 10 days

    def test_preserves_original_order(self):
        """Output order should match input order."""
        bars = _make_bars("2020-01-01", 10)
        shuffled = bars[::-1]  # reverse order
        result = filter_bars_to_window(shuffled, "2020-01-01", "2021-01-01")
        # All bars in, reversed order preserved
        assert result == shuffled

    def test_multi_symbol(self):
        """Bars from multiple symbols are all filtered correctly."""
        bars_a = _make_bars("2020-01-01", 10, ticker="AAPL")
        bars_b = _make_bars("2020-01-01", 10, ticker="MSFT")
        combined = bars_a + bars_b
        result = filter_bars_to_window(combined, "2020-01-03", "2020-01-08")
        # 5 bars each (days 3,4,5,6,7 exclusive end on 8)
        assert len(result) == 10
        tickers = {b.symbol.ticker for b in result}
        assert tickers == {"AAPL", "MSFT"}

    def test_window_used_with_period_split(self):
        """chronological_split + filter_bars_to_window produces 3 non-overlapping sets."""
        bars = _make_bars("2015-01-01", 365 * 5)  # 5 years of daily bars

        sp = chronological_split("2015-01-01", "2019-12-31")

        train_bars = filter_bars_to_window(bars, sp.train_start, sp.train_end)
        val_bars   = filter_bars_to_window(bars, sp.validation_start, sp.validation_end)
        # For holdout: use a day after holdout_end as exclusive bound so the last day is included
        from datetime import date, timedelta
        h_end_exclusive = (
            date.fromisoformat(sp.holdout_end) + timedelta(days=1)
        ).isoformat()
        hold_bars = filter_bars_to_window(bars, sp.holdout_start, h_end_exclusive)

        # No bar in both train and validation
        train_ids = {id(b) for b in train_bars}
        val_ids   = {id(b) for b in val_bars}
        hold_ids  = {id(b) for b in hold_bars}
        assert train_ids.isdisjoint(val_ids)
        assert train_ids.isdisjoint(hold_ids)
        assert val_ids.isdisjoint(hold_ids)

        # Together they cover most of the bars (small edge at boundaries possible)
        total_covered = len(train_bars) + len(val_bars) + len(hold_bars)
        assert total_covered > 0
        assert total_covered <= len(bars)

    def test_holdout_is_latest_bars(self):
        """Holdout window should contain bars with the latest dates."""
        bars = _make_bars("2015-01-01", 365 * 5)
        sp   = chronological_split("2015-01-01", "2019-12-31")

        train_bars = filter_bars_to_window(bars, sp.train_start, sp.train_end)
        hold_bars  = filter_bars_to_window(
            bars, sp.holdout_start,
            # include all bars from holdout_start onward
            "2099-01-01",
        )
        if train_bars and hold_bars:
            latest_train   = max(b.ts.date() for b in train_bars)
            earliest_hold  = min(b.ts.date() for b in hold_bars)
            assert earliest_hold >= latest_train
