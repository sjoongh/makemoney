# tests/test_fundamental_signals.py
"""Tests for point-in-time fundamental signal closures — no network."""
from __future__ import annotations

from datetime import date, datetime, timezone

from trader.core.events import BarEvent, Market, Symbol
from trader.research.fundamental_signals import (
    make_book_to_market,
    make_earnings_yield,
)


def _bar(ticker, d, close):
    sym = Symbol(ticker, Market.NASDAQ, "USD")
    ts = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return BarEvent(sym, ts, close, close, close, close, 1000)


# fundamentals for ticker X: equity & shares (instant), NI (quarterly)
_FUND = {
    "X": {
        "equity": [{"period_end": date(2023, 3, 31), "filed": date(2023, 4, 20), "val": 1_000.0}],
        "shares": [{"period_end": date(2023, 3, 31), "filed": date(2023, 4, 20), "val": 100.0}],
        "ni_quarterly": [
            {"period_end": date(2022, 6, 30), "filed": date(2022, 7, 20), "val": 10.0},
            {"period_end": date(2022, 9, 30), "filed": date(2022, 10, 20), "val": 10.0},
            {"period_end": date(2022, 12, 31), "filed": date(2023, 2, 15), "val": 10.0},
            {"period_end": date(2023, 3, 31), "filed": date(2023, 4, 20), "val": 20.0},
        ],
    }
}


def test_book_to_market_point_in_time():
    bm = make_book_to_market(_FUND)
    # price 5, shares 100 → mktcap 500; equity 1000 → B/M = 2.0
    hist = [_bar("X", "2023-05-01", 5.0)]
    assert abs(bm(hist) - 2.0) < 1e-9


def test_book_to_market_none_before_filed():
    bm = make_book_to_market(_FUND)
    # equity filed 2023-04-20; on 2023-04-01 nothing filed → None
    assert bm([_bar("X", "2023-04-01", 5.0)]) is None


def test_book_to_market_unknown_ticker_none():
    bm = make_book_to_market(_FUND)
    assert bm([_bar("ZZZ", "2023-05-01", 5.0)]) is None


def test_earnings_yield_ttm_point_in_time():
    ey = make_earnings_yield(_FUND)
    # on 2023-05-01 all 4 quarters filed → ttm NI = 10+10+10+20 = 50
    # price 5 × shares 100 = 500 → EY = 0.10
    assert abs(ey([_bar("X", "2023-05-01", 5.0)]) - 0.10) < 1e-9


def test_earnings_yield_none_when_fewer_than_4_quarters_filed():
    ey = make_earnings_yield(_FUND)
    # on 2023-03-01 only 3 quarters filed (Q1-2023 filed 4-20) → None
    assert ey([_bar("X", "2023-03-01", 5.0)]) is None
