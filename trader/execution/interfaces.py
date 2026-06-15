# trader/execution/interfaces.py
from __future__ import annotations
from typing import Protocol
from trader.core.events import BarEvent, OrderEvent, FillEvent

class ExecutionHandler(Protocol):
    def submit_order(self, order: OrderEvent) -> None:
        """주문 접수/큐잉. 즉시 체결하지 않는다."""
        ...
    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
        """이 봉의 '시가'에 실현된 체결 반환(다음봉 시가 체결 보장). 라이브=확인된 체결 대사."""
        ...
