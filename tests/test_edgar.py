# tests/test_edgar.py
"""Tests for EDGAR point-in-time parsing — pure, no network."""
from __future__ import annotations

from datetime import date

from trader.data import edgar


def _q(start, end, filed, val, fy):
    return {"start": start, "end": end, "filed": filed, "val": val, "fy": fy, "form": "10-Q"}


# ---------------------------------------------------------------------------
# quarterly_series — 3-month extraction + Q4 derivation + restatement
# ---------------------------------------------------------------------------

def test_quarterly_extracts_3month_spans():
    pts = [
        _q("2023-01-01", "2023-03-31", "2023-04-20", 100.0, 2023),  # ~90d
        _q("2023-01-01", "2023-06-30", "2023-07-20", 250.0, 2023),  # ~180d YTD → ignore
    ]
    s = edgar.quarterly_series(pts)
    assert len(s) == 1
    assert s[0]["val"] == 100.0
    assert s[0]["period_end"] == date(2023, 3, 31)


def test_quarterly_derives_q4_from_annual():
    pts = [
        _q("2023-01-01", "2023-03-31", "2023-04-20", 100.0, 2023),
        _q("2023-04-01", "2023-06-30", "2023-07-20", 110.0, 2023),
        _q("2023-07-01", "2023-09-30", "2023-10-20", 120.0, 2023),
        # annual FY2023 (~365d), filed in 10-K
        {"start": "2023-01-01", "end": "2023-12-31", "filed": "2024-02-15",
         "val": 500.0, "fy": 2023, "form": "10-K"},
    ]
    s = edgar.quarterly_series(pts)
    ends = {r["period_end"]: r["val"] for r in s}
    assert ends[date(2023, 12, 31)] == 500.0 - (100 + 110 + 120)  # Q4 = 170


def test_quarterly_restatement_keeps_original_filed():
    pts = [
        _q("2023-01-01", "2023-03-31", "2023-04-20", 100.0, 2023),  # original
        _q("2023-01-01", "2023-03-31", "2024-04-20", 95.0, 2023),   # restated later
    ]
    s = edgar.quarterly_series(pts)
    assert len(s) == 1
    assert s[0]["val"] == 100.0          # original, not restated 95
    assert s[0]["filed"] == date(2023, 4, 20)


# ---------------------------------------------------------------------------
# instant_series (equity / shares)
# ---------------------------------------------------------------------------

def test_instant_series_one_per_period_end():
    pts = [
        {"end": "2023-03-31", "filed": "2023-04-20", "val": 1000.0},
        {"end": "2023-03-31", "filed": "2024-04-20", "val": 900.0},   # restated
        {"end": "2023-06-30", "filed": "2023-07-20", "val": 1100.0},
    ]
    s = edgar.instant_series(pts)
    vals = {r["period_end"]: r["val"] for r in s}
    assert vals[date(2023, 3, 31)] == 1000.0   # original kept
    assert vals[date(2023, 6, 30)] == 1100.0


# ---------------------------------------------------------------------------
# point-in-time accessors
# ---------------------------------------------------------------------------

_SER = [
    {"period_end": date(2023, 3, 31), "filed": date(2023, 4, 20), "val": 100.0},
    {"period_end": date(2023, 6, 30), "filed": date(2023, 7, 20), "val": 110.0},
    {"period_end": date(2023, 9, 30), "filed": date(2023, 10, 20), "val": 120.0},
    {"period_end": date(2023, 12, 31), "filed": date(2024, 2, 15), "val": 170.0},
]


def test_as_of_uses_only_filed_before_t():
    # on 2023-08-01 only Q1 & Q2 are filed; latest period_end = Q2
    assert edgar.as_of(_SER, date(2023, 8, 1)) == 110.0
    # before anything filed
    assert edgar.as_of(_SER, date(2023, 1, 1)) is None


def test_ttm_requires_four_filed_quarters():
    # on 2023-11-01 only 3 quarters filed → None
    assert edgar.ttm_as_of(_SER, date(2023, 11, 1)) is None
    # on 2024-03-01 all 4 filed → sum
    assert edgar.ttm_as_of(_SER, date(2024, 3, 1)) == 100 + 110 + 120 + 170


def test_ttm_no_lookahead_at_filing_boundary():
    # Q4 filed 2024-02-15; the day before, only 3 quarters known → None
    assert edgar.ttm_as_of(_SER, date(2024, 2, 14)) is None
    assert edgar.ttm_as_of(_SER, date(2024, 2, 15)) == 500.0
