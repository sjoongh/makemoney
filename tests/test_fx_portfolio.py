# tests/test_fx_portfolio.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, FillEvent, Side
from trader.strategy.portfolio import Portfolio, FxRates

USD = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(): return datetime(2026,1,3,tzinfo=timezone.utc)

def test_equity_in_krw_after_usd_buy_and_mark():
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    p = Portfolio(cash={"KRW": 13_000_000.0}, fx=fx)   # 1300만원, USD현금 0
    p.deposit("USD", 2000.0)                            # 테스트 단순화: USD 현금 시드
    p.apply_fill(FillEvent(uuid4(), USD, _t(), Side.BUY, 10, 100.0, 0.0, "USD"))
    assert p.position(USD) == 10
    assert p.cash["USD"] == 1000.0
    p.mark(BarEvent(USD, _t(), 110,110,110,110, 1))     # 종가 $110
    assert round(p.equity_krw()) == round(13_000_000 + 1000*1300 + 10*110*1300)
