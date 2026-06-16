# trader/data/quality.py
"""Data quality validation pipeline.

Run BEFORE trusting any dataset in research:
    python -m trader.app.validate_data --all
    python -m trader.app.validate_data research_data/KOSPI_005930.parquet

Every dataset must produce a pass/fail QualityReport before use.
A FAIL severity issue means data is not safe to use.
A WARN severity issue means data may have quality concerns worth investigating.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from trader.core.events import BarEvent
from trader.data.storage import load_bars


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: str  # "WARN" | "FAIL"
    detail: str
    count: int = 1


@dataclass
class QualityReport:
    symbol: str
    n_bars: int
    start: Optional[datetime]
    end: Optional[datetime]
    issues: List[QualityIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True if no FAIL-severity issues. WARN-only reports pass."""
        return not any(i.severity == "FAIL" for i in self.issues)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"[{status}] {self.symbol}  bars={self.n_bars}  "
            f"range={self.start} → {self.end}"
        ]
        if not self.issues:
            lines.append("  No issues found.")
        for issue in self.issues:
            lines.append(
                f"  [{issue.severity}] {issue.code} (count={issue.count}): {issue.detail}"
            )
        return "\n".join(lines)


def validate_bars(
    bars: List[BarEvent],
    *,
    expected_calendar=None,
    max_daily_return: float = 0.40,
    max_stale_run: int = 5,
) -> QualityReport:
    """Validate a list of BarEvents and return a QualityReport.

    Parameters
    ----------
    bars:
        The bar data to validate.
    expected_calendar:
        Optional list of expected trading day datetimes. Currently unused
        (documented TODO: integrate exchange-calendars for full holiday check).
    max_daily_return:
        Threshold for flagging extreme single-day close-to-close returns as WARN.
        Default 0.40 (40%).
    max_stale_run:
        Maximum consecutive bars with identical close before flagging stale run.
        Default 5.
    """
    # Determine symbol name for the report
    symbol_name = bars[0].symbol.ticker if bars else "UNKNOWN"

    # --- FAIL: empty / too few bars ---
    if len(bars) < 2:
        return QualityReport(
            symbol=symbol_name,
            n_bars=len(bars),
            start=bars[0].ts if bars else None,
            end=bars[0].ts if bars else None,
            issues=[
                QualityIssue(
                    code="TOO_FEW_BARS",
                    severity="FAIL",
                    detail=f"Need at least 2 bars; got {len(bars)}.",
                    count=len(bars),
                )
            ],
        )

    issues: List[QualityIssue] = []
    n = len(bars)
    start_ts = bars[0].ts
    end_ts = bars[-1].ts

    # --- FAIL: duplicate timestamps ---
    timestamps = [b.ts for b in bars]
    ts_counts: dict = {}
    for ts in timestamps:
        ts_counts[ts] = ts_counts.get(ts, 0) + 1
    dup_count = sum(1 for c in ts_counts.values() if c > 1)
    if dup_count:
        issues.append(
            QualityIssue(
                code="DUPLICATE_TIMESTAMPS",
                severity="FAIL",
                detail=f"{dup_count} timestamp(s) appear more than once.",
                count=dup_count,
            )
        )

    # --- FAIL: not sorted ascending by ts ---
    unsorted_count = sum(
        1 for i in range(1, n) if bars[i].ts <= bars[i - 1].ts
    )
    if unsorted_count:
        issues.append(
            QualityIssue(
                code="NOT_SORTED",
                severity="FAIL",
                detail=f"{unsorted_count} bar(s) out of ascending timestamp order.",
                count=unsorted_count,
            )
        )

    # --- FAIL: non-positive OHLC or negative volume ---
    bad_price_count = 0
    for b in bars:
        if b.open <= 0 or b.high <= 0 or b.low <= 0 or b.close <= 0 or b.volume < 0:
            bad_price_count += 1
    if bad_price_count:
        issues.append(
            QualityIssue(
                code="NONPOSITIVE_PRICE_OR_NEG_VOLUME",
                severity="FAIL",
                detail=(
                    f"{bad_price_count} bar(s) with non-positive OHLC or negative volume."
                ),
                count=bad_price_count,
            )
        )

    # --- FAIL: OHLC consistency ---
    ohlc_bad_count = 0
    for b in bars:
        expected_high = max(b.open, b.close, b.low)
        expected_low = min(b.open, b.close, b.high)
        if b.high < expected_high or b.low > expected_low or b.high < b.low:
            ohlc_bad_count += 1
    if ohlc_bad_count:
        issues.append(
            QualityIssue(
                code="OHLC_INCONSISTENT",
                severity="FAIL",
                detail=(
                    f"{ohlc_bad_count} bar(s) violate OHLC consistency "
                    "(high < max(O,C,L) or low > min(O,C,H) or high < low)."
                ),
                count=ohlc_bad_count,
            )
        )

    # --- WARN: extreme daily return (>max_daily_return) ---
    # Also catches split-like jumps that reverse; the heuristic here is simply
    # flagging any >40% single-day move. A reversal within the next bar would
    # appear as two consecutive extreme-return flags. TODO: refine split detection
    # using a dedicated split-adjustment check.
    extreme_return_count = 0
    for i in range(1, n):
        prev_close = bars[i - 1].close
        curr_close = bars[i].close
        if prev_close > 0:
            ret = abs(curr_close / prev_close - 1.0)
            if ret > max_daily_return:
                extreme_return_count += 1
    if extreme_return_count:
        issues.append(
            QualityIssue(
                code="EXTREME_RETURN",
                severity="WARN",
                detail=(
                    f"{extreme_return_count} bar(s) with |close-to-close return| > "
                    f"{max_daily_return:.0%}. Possible split, bad bar, or data error. "
                    "Consecutive extreme moves may indicate a split that reverses."
                ),
                count=extreme_return_count,
            )
        )

    # --- WARN: stale price run (close unchanged for >max_stale_run consecutive bars) ---
    stale_warn_count = 0
    stale_run = 1
    for i in range(1, n):
        if bars[i].close == bars[i - 1].close:
            stale_run += 1
            if stale_run == max_stale_run + 1:
                stale_warn_count += 1
        else:
            stale_run = 1
    if stale_warn_count:
        issues.append(
            QualityIssue(
                code="STALE_PRICE_RUN",
                severity="WARN",
                detail=(
                    f"{stale_warn_count} run(s) of >{max_stale_run} consecutive bars "
                    "with unchanged close price. Possible stale/frozen data feed."
                ),
                count=stale_warn_count,
            )
        )

    # --- WARN: zero-volume bars ---
    zero_vol_count = sum(1 for b in bars if b.volume == 0)
    if zero_vol_count:
        issues.append(
            QualityIssue(
                code="ZERO_VOLUME",
                severity="WARN",
                detail=f"{zero_vol_count} bar(s) with zero volume.",
                count=zero_vol_count,
            )
        )

    # --- WARN: large calendar gaps (>5 weekdays between consecutive bars) ---
    # Simple weekday-gap heuristic. Full exchange-holiday calendar is a TODO:
    # replace with exchange-calendars library for holiday-aware gap detection.
    calendar_gap_count = 0
    for i in range(1, n):
        t_prev = bars[i - 1].ts
        t_curr = bars[i].ts
        # Count weekdays between t_prev and t_curr (exclusive of t_prev)
        gap_days = (t_curr.date() - t_prev.date()).days
        if gap_days <= 0:
            continue
        # Approximate weekday count: total days minus weekends
        weekday_gap = 0
        check = t_prev.date() + timedelta(days=1)
        end_date = t_curr.date()
        # For large gaps we count; for small gaps fast-path
        if gap_days > 14:
            # rough approximation: 5/7 of calendar days are weekdays
            weekday_gap = gap_days - 2 * ((gap_days + t_prev.date().weekday()) // 7)
        else:
            d = check
            while d < end_date:
                if d.weekday() < 5:
                    weekday_gap += 1
                d += timedelta(days=1)
        if weekday_gap > 5:
            calendar_gap_count += 1
    if calendar_gap_count:
        issues.append(
            QualityIssue(
                code="CALENDAR_GAP",
                severity="WARN",
                detail=(
                    f"{calendar_gap_count} consecutive bar pair(s) with >5 weekdays gap. "
                    "Possible missing sessions. "
                    "TODO: integrate exchange-calendars for holiday-aware detection."
                ),
                count=calendar_gap_count,
            )
        )

    return QualityReport(
        symbol=symbol_name,
        n_bars=n,
        start=start_ts,
        end=end_ts,
        issues=issues,
    )


def validate_parquet(path: str) -> QualityReport:
    """Load bars from a parquet file and validate them.

    Parameters
    ----------
    path:
        Path to the parquet file produced by trader.data.storage.save_bars.
    """
    bars = load_bars(path)
    return validate_bars(bars)
