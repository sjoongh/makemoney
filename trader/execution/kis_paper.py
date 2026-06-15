# trader/execution/kis_paper.py
from __future__ import annotations
from uuid import uuid4
from trader.core.events import BarEvent, OrderEvent, FillEvent, Symbol, Market, Side

class KisPaperExecutionHandler:
    """KIS 모의투자 실행. submit_order=KIS 제출, on_bar=확인된 체결만 FillEvent로 대사.
    주문 제출 != 체결 — 포트폴리오는 확인 체결로만 갱신."""
    def __init__(self, kis_client):
        self._kis = kis_client

    def submit_order(self, order: OrderEvent) -> None:
        self._kis.submit_order(order.symbol.ticker, order.symbol.market.value,
                               order.side.value, order.quantity)

    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
        out: list[FillEvent] = []
        for f in self._kis.filled_orders():
            sym = Symbol(f["ticker"], Market(f["market"]), f["currency"])
            out.append(FillEvent(uuid4(), sym, bar.ts, Side(f["side"]), int(f["qty"]),
                                 float(f["price"]), float(f["commission"]), f["currency"]))
        return out
