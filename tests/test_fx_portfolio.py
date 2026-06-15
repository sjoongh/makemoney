# tests/test_fx_portfolio.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, BarEvent, FillEvent, Side
from trader.strategy.portfolio import Portfolio, FxRates

USD = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(): return datetime(2026,1,3,tzinfo=timezone.utc)

def test_same_ticker_different_markets_do_not_collide():
    from uuid import uuid4
    from datetime import datetime, timezone
    from trader.core.events import Symbol, Market, FillEvent, Side
    a = Symbol("X", Market.NASDAQ, "USD")
    b = Symbol("X", Market.KOSPI, "KRW")   # 같은 티커, 다른 시장
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    p = Portfolio({"KRW":10_000_000.0,"USD":10_000.0}, fx)
    t = datetime(2026,1,3,tzinfo=timezone.utc)
    p.apply_fill(FillEvent(uuid4(), a, t, Side.BUY, 3, 100.0, 0.0, "USD"))
    p.apply_fill(FillEvent(uuid4(), b, t, Side.BUY, 7, 5000.0, 0.0, "KRW"))
    assert p.position(a) == 3 and p.position(b) == 7   # 충돌하지 않음

def test_usd_buy_settles_in_krw_and_equity():
    from uuid import uuid4
    fx = FxRates({"USD": 1300.0, "KRW": 1.0})
    p = Portfolio(cash={"KRW": 13_000_000.0}, fx=fx)
    p.apply_fill(FillEvent(uuid4(), USD, _t(), Side.BUY, 10, 100.0, 0.0, "USD"))
    assert p.position(USD) == 10
    # 외화 매수가 KRW 현금에서 자동환전 차감: 10*100*1300 = 1,300,000
    assert round(p.cash["KRW"]) == 13_000_000 - 10*100*1300
    p.mark(BarEvent(USD, _t(), 110,110,110,110, 1))
    # equity = KRW현금 + 포지션(110*10*1300)
    assert round(p.equity_krw()) == round(13_000_000 - 10*100*1300 + 10*110*1300)
