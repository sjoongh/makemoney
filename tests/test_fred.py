# tests/test_fred.py
"""Tests for FRED parsing + point-in-time accessor — no network."""
from __future__ import annotations

from datetime import date

from trader.data import fred

_CSV = """observation_date,T10Y2Y
2023-01-02,0.50
2023-01-03,.
2023-01-04,-0.10
bad,row
2023-01-05,0.20
"""


def test_parse_skips_missing_and_bad():
    s = fred.parse_fred_csv(_CSV)
    assert s == [
        (date(2023, 1, 2), 0.50),
        (date(2023, 1, 4), -0.10),
        (date(2023, 1, 5), 0.20),
    ]


def test_as_of_value_point_in_time():
    s = fred.parse_fred_csv(_CSV)
    assert fred.as_of_value(s, date(2023, 1, 4)) == -0.10   # latest <= t
    assert fred.as_of_value(s, date(2023, 1, 3)) == 0.50    # uses 1-02 (1-03 missing)
    assert fred.as_of_value(s, date(2022, 12, 31)) is None  # before first obs
