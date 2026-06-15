import httpx
from trader.execution.kis_client import KisClient

def _mock(handler): return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://mock")

def test_daily_bars_normalize_for_nasdaq_and_kospi():
    def handler(req):
        return httpx.Response(200, json={"output":[{"date":"20260102","open":"10","high":"11","low":"9","close":"10.5","volume":"100"}]})
    c = KisClient(client=_mock(handler), app_key="k", app_secret="s", account="acct", paper=True)
    bars = c.daily_bars(ticker="AAPL", market="NASDAQ", currency="USD")
    assert len(bars) == 1 and bars[0].close == 10.5 and bars[0].symbol.currency == "USD"
    bars_kr = c.daily_bars(ticker="005930", market="KOSPI", currency="KRW")
    assert bars_kr[0].symbol.currency == "KRW"
