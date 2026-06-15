from __future__ import annotations
from trader.core.events import BarEvent, OrderEvent, FillEvent
from trader.execution.costs import BpsCostModel

class SimulatedExecutionHandler:
    """주문은 큐잉, 체결은 다음 호출되는 on_bar의 '시가'에 실현 → 룩어헤드 구조적 차단."""
    def __init__(self, cost_model: BpsCostModel | None = None):
        self._cost = cost_model or BpsCostModel(0.0)
        self._pending: list[OrderEvent] = []
    def submit_order(self, order: OrderEvent) -> None:
        self._pending.append(order)
    def on_bar(self, bar: BarEvent) -> list[FillEvent]:
        fills: list[FillEvent] = []
        still: list[OrderEvent] = []
        for o in self._pending:
            if o.symbol == bar.symbol:
                price = bar.open
                fills.append(FillEvent(o.order_id, o.symbol, bar.ts, o.side,
                                       o.quantity, price,
                                       self._cost.commission(price, o.quantity),
                                       o.symbol.currency))
            else:
                still.append(o)
        self._pending = still
        return fills
