# trader/execution/kis_paper.py
from __future__ import annotations
from uuid import UUID, uuid4
from trader.core.events import BarEvent, OrderEvent, FillEvent, Symbol, Market, Side

class KisPaperExecutionHandler:
    """KIS 모의투자 실행. submit_order=KIS 제출, on_bar=확인된 체결만 FillEvent로 대사.
    주문 제출 != 체결 — 포트폴리오는 확인 체결로만 갱신.
    동일 체결 중복 적용 방지: 브로커 order_id를 seen set으로 관리."""
    def __init__(self, kis_client):
        self._kis = kis_client
        self._broker_to_order_id: dict[str, UUID] = {}   # broker_id -> original order UUID
        self._seen_fill_ids: set[str] = set()            # 이미 처리한 브로커 체결 id

    def submit_order(self, order: OrderEvent) -> None:
        broker_id = self._kis.submit_order(order.symbol.ticker, order.symbol.market.value,
                                           order.side.value, order.quantity)
        if broker_id is not None:
            self._broker_to_order_id[broker_id] = order.order_id

    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
        out: list[FillEvent] = []
        for f in self._kis.filled_orders():
            broker_fill_id = f["order_id"]
            if broker_fill_id in self._seen_fill_ids:
                continue  # 이미 처리한 체결 — 무시
            self._seen_fill_ids.add(broker_fill_id)
            order_id = self._broker_to_order_id.get(broker_fill_id, uuid4())
            sym = Symbol(f["ticker"], Market(f["market"]), f["currency"])
            out.append(FillEvent(order_id, sym, bar.ts, Side(f["side"]), int(f["qty"]),
                                 float(f["price"]), float(f["commission"]), f["currency"]))
        return out
