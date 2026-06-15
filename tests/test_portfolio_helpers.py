# tests/test_portfolio_helpers.py
"""TDD tests for Portfolio exposure helper methods."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from trader.core.events import Symbol, Market, BarEvent, FillEvent, Side
from trader.strategy.portfolio import Portfolio, FxRates

USD_SYM = Symbol("AAPL", Market.NASDAQ, "USD")
KRW_SYM = Symbol("005930", Market.KOSPI, "KRW")

def _ts():
    return datetime(2026, 1, 1, tzinfo=timezone.utc)

def _bar(sym: Symbol, close: float) -> BarEvent:
    return BarEvent(sym, _ts(), close, close, close, close, 100)

def _fill(sym: Symbol, qty: int, price: float, ccy: str) -> FillEvent:
    return FillEvent(uuid4(), sym, _ts(), Side.BUY, qty, price, 0.0, ccy)


def _make_portfolio() -> Portfolio:
    """
    Portfolio with:
      - 10 AAPL @ $100 USD  → 10*100*1300 = 1,300,000 KRW position value
      - 5  005930 @ 50000 KRW → 5*50000*1 = 250,000 KRW position value
      - cash KRW 1,000,000
      Total equity = 1,300,000 + 250,000 + 1,000,000 = 2,550,000 KRW
    """
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    # Start with enough cash to cover buys
    pf = Portfolio({"KRW": 3_000_000.0}, fx)
    pf.apply_fill(_fill(USD_SYM, 10, 100.0, "USD"))   # cost = 10*100*1300 = 1,300,000 KRW
    pf.apply_fill(_fill(KRW_SYM, 5, 50_000.0, "KRW")) # cost = 5*50000 = 250,000 KRW
    # mark both so _mark is set
    pf.mark(_bar(USD_SYM, 100.0))
    pf.mark(_bar(KRW_SYM, 50_000.0))
    # remaining cash = 3,000,000 - 1,300,000 - 250,000 = 1,450,000 KRW
    return pf


def test_position_value_krw_usd_symbol():
    pf = _make_portfolio()
    # 10 shares * $100 * 1300 = 1,300,000 KRW
    assert pf.position_value_krw(USD_SYM) == 1_300_000.0


def test_position_value_krw_krw_symbol():
    pf = _make_portfolio()
    # 5 shares * 50000 KRW = 250,000 KRW
    assert pf.position_value_krw(KRW_SYM) == 250_000.0


def test_position_value_krw_no_position():
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 1_000_000.0}, fx)
    assert pf.position_value_krw(USD_SYM) == 0.0


def test_position_weight_usd_symbol():
    pf = _make_portfolio()
    equity = pf.equity_krw()
    expected = 1_300_000.0 / equity
    assert abs(pf.position_weight(USD_SYM) - expected) < 1e-9


def test_position_weight_zero_equity():
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 0.0}, fx)
    assert pf.position_weight(USD_SYM) == 0.0


def test_market_weight_nasdaq():
    pf = _make_portfolio()
    equity = pf.equity_krw()
    # Only AAPL (NASDAQ): 1,300,000 KRW
    expected = 1_300_000.0 / equity
    assert abs(pf.market_weight(Market.NASDAQ) - expected) < 1e-9


def test_market_weight_kospi():
    pf = _make_portfolio()
    equity = pf.equity_krw()
    # Only 005930 (KOSPI): 250,000 KRW
    expected = 250_000.0 / equity
    assert abs(pf.market_weight(Market.KOSPI) - expected) < 1e-9


def test_market_weight_unknown_market():
    pf = _make_portfolio()
    # No positions in some other market → weight should be 0
    # We use KOSPI but with no positions
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf2 = Portfolio({"KRW": 1_000_000.0}, fx)
    assert pf2.market_weight(Market.KOSPI) == 0.0


def test_open_position_count_two_symbols():
    pf = _make_portfolio()
    assert pf.open_position_count() == 2


def test_open_position_count_zero():
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 1_000_000.0}, fx)
    assert pf.open_position_count() == 0


def test_open_position_count_excludes_zero_qty():
    """A position that goes to zero should not be counted."""
    from trader.core.events import FillEvent, Side
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    pf = Portfolio({"KRW": 3_000_000.0}, fx)
    pf.apply_fill(_fill(USD_SYM, 10, 100.0, "USD"))
    # sell same amount → zero net position
    sell = FillEvent(uuid4(), USD_SYM, _ts(), Side.SELL, 10, 100.0, 0.0, "USD")
    pf.apply_fill(sell)
    assert pf.open_position_count() == 0
