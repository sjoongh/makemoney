# tests/test_quality.py
"""Synthetic, deterministic tests for trader.data.quality."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from trader.core.events import BarEvent, Symbol, Market
from trader.data.quality import QualityIssue, QualityReport, validate_bars

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SYM = Symbol("TEST", Market.KOSPI, "KRW")
T0 = datetime(2024, 1, 2, tzinfo=timezone.utc)  # Tuesday


def _bar(i: int, close: float, open_: float | None = None, high: float | None = None,
         low: float | None = None, volume: int = 1000) -> BarEvent:
    """Create a bar i days after T0 with sane OHLC defaults derived from close."""
    c = close
    o = open_ if open_ is not None else c
    h = high if high is not None else max(o, c) * 1.001
    lo = low if low is not None else min(o, c) * 0.999
    ts = T0 + timedelta(days=i)
    return BarEvent(SYM, ts, o, h, lo, c, volume)


def _clean_bars(n: int = 10) -> list[BarEvent]:
    """Ascending clean bars with normal prices."""
    return [_bar(i, close=100.0 + i) for i in range(n)]


# ---------------------------------------------------------------------------
# QualityIssue / QualityReport dataclass behaviour
# ---------------------------------------------------------------------------

class TestQualityIssueDataclass:
    def test_frozen(self):
        issue = QualityIssue(code="X", severity="FAIL", detail="d")
        with pytest.raises((AttributeError, TypeError)):
            issue.code = "Y"  # type: ignore[misc]

    def test_default_count(self):
        issue = QualityIssue(code="X", severity="WARN", detail="d")
        assert issue.count == 1


class TestQualityReportPassedProperty:
    def test_no_issues_passed(self):
        r = QualityReport(symbol="X", n_bars=10, start=T0, end=T0, issues=[])
        assert r.passed is True

    def test_warn_only_passed(self):
        r = QualityReport(
            symbol="X", n_bars=10, start=T0, end=T0,
            issues=[QualityIssue("ZERO_VOLUME", "WARN", "z", 1)],
        )
        assert r.passed is True

    def test_fail_not_passed(self):
        r = QualityReport(
            symbol="X", n_bars=10, start=T0, end=T0,
            issues=[QualityIssue("DUPLICATE_TIMESTAMPS", "FAIL", "d", 1)],
        )
        assert r.passed is False

    def test_mixed_fail_and_warn_not_passed(self):
        r = QualityReport(
            symbol="X", n_bars=10, start=T0, end=T0,
            issues=[
                QualityIssue("ZERO_VOLUME", "WARN", "z", 1),
                QualityIssue("DUPLICATE_TIMESTAMPS", "FAIL", "d", 1),
            ],
        )
        assert r.passed is False

    def test_summary_contains_pass_status(self):
        r = QualityReport(symbol="X", n_bars=5, start=T0, end=T0, issues=[])
        assert "PASS" in r.summary()

    def test_summary_contains_fail_status(self):
        r = QualityReport(
            symbol="X", n_bars=5, start=T0, end=T0,
            issues=[QualityIssue("X", "FAIL", "d")],
        )
        assert "FAIL" in r.summary()


# ---------------------------------------------------------------------------
# Clean data → passed, no FAIL
# ---------------------------------------------------------------------------

class TestCleanData:
    def test_clean_ascending_passes(self):
        report = validate_bars(_clean_bars(20))
        assert report.passed is True

    def test_clean_no_fail_issues(self):
        report = validate_bars(_clean_bars(20))
        fail_issues = [i for i in report.issues if i.severity == "FAIL"]
        assert fail_issues == []

    def test_report_metadata(self):
        bars = _clean_bars(10)
        report = validate_bars(bars)
        assert report.symbol == "TEST"
        assert report.n_bars == 10
        assert report.start == bars[0].ts
        assert report.end == bars[-1].ts


# ---------------------------------------------------------------------------
# FAIL cases
# ---------------------------------------------------------------------------

class TestTooFewBars:
    def test_zero_bars(self):
        report = validate_bars([])
        assert report.passed is False
        codes = {i.code for i in report.issues}
        assert "TOO_FEW_BARS" in codes

    def test_one_bar(self):
        report = validate_bars([_bar(0, 100.0)])
        assert report.passed is False
        codes = {i.code for i in report.issues}
        assert "TOO_FEW_BARS" in codes

    def test_two_bars_ok(self):
        report = validate_bars([_bar(0, 100.0), _bar(1, 101.0)])
        fail_codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "TOO_FEW_BARS" not in fail_codes


class TestDuplicateTimestamps:
    def test_duplicate_ts_is_fail(self):
        bars = _clean_bars(5)
        # Inject a duplicate: copy bar[2] with same ts
        dup = BarEvent(SYM, bars[2].ts, 100, 101, 99, 100, 500)
        bars_with_dup = bars[:3] + [dup] + bars[3:]
        report = validate_bars(bars_with_dup)
        assert report.passed is False
        codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "DUPLICATE_TIMESTAMPS" in codes

    def test_duplicate_count_reported(self):
        bars = _clean_bars(5)
        dup = BarEvent(SYM, bars[1].ts, 100, 101, 99, 100, 500)
        bars_with_dup = [bars[0], bars[1], dup] + bars[2:]
        report = validate_bars(bars_with_dup)
        dup_issues = [i for i in report.issues if i.code == "DUPLICATE_TIMESTAMPS"]
        assert len(dup_issues) == 1
        assert dup_issues[0].count >= 1


class TestUnsorted:
    def test_unsorted_is_fail(self):
        bars = _clean_bars(5)
        # Swap bars[1] and bars[2] to break sort order
        bars[1], bars[2] = bars[2], bars[1]
        report = validate_bars(bars)
        assert report.passed is False
        codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "NOT_SORTED" in codes


class TestOHLCConsistency:
    def test_high_less_than_low_is_fail(self):
        # high < low: completely inverted
        ts = T0
        bar = BarEvent(SYM, ts, 100.0, 90.0, 110.0, 100.0, 1000)  # high=90 < low=110
        bars = [_bar(0, 100.0), bar]
        # Need a second bar — use bar as bars[1]
        bars = [_bar(0, 100.0), BarEvent(SYM, T0 + timedelta(days=1), 100.0, 90.0, 110.0, 100.0, 1000)]
        report = validate_bars(bars)
        assert report.passed is False
        codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "OHLC_INCONSISTENT" in codes

    def test_high_below_close_is_fail(self):
        # high < close: impossible
        bars = [
            _bar(0, 100.0),
            BarEvent(SYM, T0 + timedelta(days=1), 100.0, 95.0, 99.0, 110.0, 1000),  # high=95 < close=110
        ]
        report = validate_bars(bars)
        assert report.passed is False
        codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "OHLC_INCONSISTENT" in codes

    def test_ohlc_count_in_report(self):
        bars = []
        for i in range(3):
            bars.append(_bar(i, 100.0))
        # Add 2 bad bars
        bars.append(BarEvent(SYM, T0 + timedelta(days=3), 100.0, 90.0, 110.0, 100.0, 500))
        bars.append(BarEvent(SYM, T0 + timedelta(days=4), 100.0, 90.0, 110.0, 100.0, 500))
        report = validate_bars(bars)
        ohlc_issues = [i for i in report.issues if i.code == "OHLC_INCONSISTENT"]
        assert len(ohlc_issues) == 1
        assert ohlc_issues[0].count == 2


class TestNegativePrice:
    def test_negative_close_is_fail(self):
        bars = [
            _bar(0, 100.0),
            BarEvent(SYM, T0 + timedelta(days=1), 100.0, 110.0, 90.0, -5.0, 1000),
        ]
        report = validate_bars(bars)
        assert report.passed is False
        codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "NONPOSITIVE_PRICE_OR_NEG_VOLUME" in codes

    def test_zero_open_is_fail(self):
        bars = [
            _bar(0, 100.0),
            BarEvent(SYM, T0 + timedelta(days=1), 0.0, 110.0, 90.0, 100.0, 1000),
        ]
        report = validate_bars(bars)
        assert report.passed is False
        codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "NONPOSITIVE_PRICE_OR_NEG_VOLUME" in codes

    def test_negative_volume_is_fail(self):
        bars = [
            _bar(0, 100.0),
            BarEvent(SYM, T0 + timedelta(days=1), 100.0, 110.0, 90.0, 100.0, -1),
        ]
        report = validate_bars(bars)
        assert report.passed is False
        codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "NONPOSITIVE_PRICE_OR_NEG_VOLUME" in codes


# ---------------------------------------------------------------------------
# WARN cases  (these must NOT produce FAIL → passed=True)
# ---------------------------------------------------------------------------

class TestExtremeReturn:
    def test_50pct_jump_is_warn_not_fail(self):
        # 100 → 150: 50% jump
        bars = [_bar(0, 100.0), _bar(1, 150.0)] + [_bar(i, 150.0) for i in range(2, 5)]
        report = validate_bars(bars)
        assert report.passed is True  # WARN only, still passes
        warn_codes = {i.code for i in report.issues if i.severity == "WARN"}
        assert "EXTREME_RETURN" in warn_codes
        fail_codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "EXTREME_RETURN" not in fail_codes

    def test_40pct_jump_boundary(self):
        # Exactly 40% — at boundary, should NOT trigger (must be strictly greater)
        bars = [_bar(0, 100.0), _bar(1, 140.0)] + [_bar(i, 140.0) for i in range(2, 5)]
        report = validate_bars(bars)
        er_issues = [i for i in report.issues if i.code == "EXTREME_RETURN"]
        assert len(er_issues) == 0  # 40% is not > 40%

    def test_41pct_jump_triggers(self):
        bars = [_bar(0, 100.0), _bar(1, 141.0)] + [_bar(i, 141.0) for i in range(2, 5)]
        report = validate_bars(bars)
        er_issues = [i for i in report.issues if i.code == "EXTREME_RETURN"]
        assert len(er_issues) == 1
        assert er_issues[0].severity == "WARN"

    def test_extreme_return_count(self):
        # Two extreme return events
        bars = [
            _bar(0, 100.0),
            _bar(1, 160.0),   # +60%
            _bar(2, 160.0),
            _bar(3, 250.0),   # +56%
            _bar(4, 250.0),
        ]
        report = validate_bars(bars)
        er_issues = [i for i in report.issues if i.code == "EXTREME_RETURN"]
        assert er_issues[0].count == 2


class TestStaleRun:
    def test_stale_run_of_6_is_warn(self):
        # 6 consecutive bars with same close > default max_stale_run of 5
        bars = [_bar(i, 100.0 + i) for i in range(3)]  # normal lead-in
        stale_close = 105.0
        for i in range(3, 9):  # 6 identical closes
            bars.append(_bar(i, stale_close))
        report = validate_bars(bars)
        assert report.passed is True
        warn_codes = {i.code for i in report.issues if i.severity == "WARN"}
        assert "STALE_PRICE_RUN" in warn_codes

    def test_exactly_max_stale_run_no_warn(self):
        # Exactly 5 unchanged: should NOT warn (must exceed max_stale_run)
        bars = [_bar(0, 100.0)] + [_bar(i, 100.0) for i in range(1, 5)]
        report = validate_bars(bars)  # 5 total bars, 4 unchanged
        stale_issues = [i for i in report.issues if i.code == "STALE_PRICE_RUN"]
        assert len(stale_issues) == 0

    def test_stale_run_just_over_threshold(self):
        # 6 consecutive identical closes → exactly 1 stale run flagged
        bars = [_bar(i, 100.0) for i in range(7)]  # 7 bars all same close
        report = validate_bars(bars)
        stale_issues = [i for i in report.issues if i.code == "STALE_PRICE_RUN"]
        assert len(stale_issues) == 1
        assert stale_issues[0].severity == "WARN"


class TestZeroVolume:
    def test_zero_volume_is_warn(self):
        bars = _clean_bars(5)
        # Replace bar[2] with zero volume
        b = bars[2]
        bars[2] = BarEvent(b.symbol, b.ts, b.open, b.high, b.low, b.close, 0)
        report = validate_bars(bars)
        assert report.passed is True
        warn_codes = {i.code for i in report.issues if i.severity == "WARN"}
        assert "ZERO_VOLUME" in warn_codes

    def test_zero_volume_not_fail(self):
        bars = _clean_bars(5)
        b = bars[1]
        bars[1] = BarEvent(b.symbol, b.ts, b.open, b.high, b.low, b.close, 0)
        report = validate_bars(bars)
        fail_codes = {i.code for i in report.issues if i.severity == "FAIL"}
        assert "ZERO_VOLUME" not in fail_codes

    def test_zero_volume_count(self):
        bars = _clean_bars(5)
        for idx in [1, 3]:
            b = bars[idx]
            bars[idx] = BarEvent(b.symbol, b.ts, b.open, b.high, b.low, b.close, 0)
        report = validate_bars(bars)
        zv = [i for i in report.issues if i.code == "ZERO_VOLUME"]
        assert zv[0].count == 2


# ---------------------------------------------------------------------------
# Calendar gap WARN
# ---------------------------------------------------------------------------

class TestCalendarGap:
    def test_large_gap_is_warn(self):
        # Two bars 15 days apart (> 5 weekdays)
        bars = [
            _bar(0, 100.0),
            BarEvent(SYM, T0 + timedelta(days=15), 100.0, 101.0, 99.0, 100.0, 1000),
        ]
        report = validate_bars(bars)
        warn_codes = {i.code for i in report.issues if i.severity == "WARN"}
        assert "CALENDAR_GAP" in warn_codes

    def test_small_gap_no_warn(self):
        # Normal 1-day gap
        bars = [_bar(0, 100.0), _bar(1, 101.0)]
        report = validate_bars(bars)
        gap_issues = [i for i in report.issues if i.code == "CALENDAR_GAP"]
        assert len(gap_issues) == 0


# ---------------------------------------------------------------------------
# passed property: WARN-only → True; any FAIL → False
# ---------------------------------------------------------------------------

class TestPassedPropertyCombinations:
    def test_warn_only_passed_true(self):
        # Zero volume is WARN; report should pass
        bars = _clean_bars(5)
        b = bars[2]
        bars[2] = BarEvent(b.symbol, b.ts, b.open, b.high, b.low, b.close, 0)
        report = validate_bars(bars)
        assert report.passed is True

    def test_fail_issue_passed_false(self):
        # Duplicate ts → FAIL
        bars = _clean_bars(5)
        dup = BarEvent(SYM, bars[2].ts, 100, 101, 99, 100, 500)
        bars_with_dup = bars[:3] + [dup] + bars[3:]
        report = validate_bars(bars_with_dup)
        assert report.passed is False

    def test_multiple_fails_passed_false(self):
        # Unsorted + negative price
        bars = [
            _bar(1, 100.0),
            _bar(0, 100.0),  # out of order
        ]
        report = validate_bars(bars)
        assert report.passed is False

    def test_no_issues_passed_true(self):
        report = validate_bars(_clean_bars(10))
        assert report.passed is True
        assert report.issues == []
