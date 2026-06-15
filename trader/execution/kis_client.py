# trader/execution/kis_client.py
from __future__ import annotations
from datetime import datetime, timezone
import httpx
from trader.core.events import BarEvent, Symbol, Market

class KisClient:
    """KIS REST 래퍼. 국내/해외 차이(엔드포인트·호가단위·통화·TR_ID)를 이 안에 격리.
    외부에는 표준 BarEvent / 주문 인터페이스만 노출."""
    def __init__(self, client: httpx.Client, app_key: str, app_secret: str, account: str, paper: bool = True):
        self._c = client; self.app_key = app_key; self.app_secret = app_secret
        self.account = account; self.paper = paper

    def _parse_bar(self, row: dict, sym: Symbol) -> BarEvent:
        ts = datetime.strptime(row["date"], "%Y%m%d").replace(tzinfo=timezone.utc)
        return BarEvent(sym, ts, float(row["open"]), float(row["high"]), float(row["low"]),
                        float(row["close"]), int(float(row["volume"])))

    def daily_bars(self, ticker: str, market: str, currency: str) -> list[BarEvent]:
        sym = Symbol(ticker, Market(market), currency)
        path = "/overseas/daily" if market == "NASDAQ" else "/domestic/daily"  # 실제 KIS 경로로 교체
        r = self._c.get(path, params={"symbol": ticker})
        r.raise_for_status()
        return [self._parse_bar(row, sym) for row in r.json()["output"]]

    def submit_order(self, ticker: str, market: str, side: str, quantity: int) -> str:
        path = "/overseas/order" if market == "NASDAQ" else "/domestic/order"  # 실제 KIS 경로로 교체
        r = self._c.post(path, json={"symbol": ticker, "side": side, "qty": quantity})
        r.raise_for_status()
        return r.json().get("order_id", "")

    def filled_orders(self) -> list[dict]:
        r = self._c.get("/orders/filled"); r.raise_for_status()
        return r.json().get("output", [])
