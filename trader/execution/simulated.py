from __future__ import annotations
from trader.core.events import BarEvent, OrderEvent, FillEvent
from trader.execution.costs import BpsCostModel

class SimulatedExecutionHandler:
    """주문은 큐잉, 체결은 다음 호출되는 on_bar의 '시가'에 실현 → 룩어헤드 구조적 차단.

    주문 수명 정책(의도적): 시장가 주문은 '해당 심볼의 다음 봉'에서 체결된다. 심볼이
    재출현하지 않으면(상장폐지/데이터갭/피드 종료) 그 주문은 **체결을 만들지 않고**
    엔진 종료 시 함께 폐기된다 — 미래 시점의 유령 체결은 절대 생성하지 않는다.
    라이브(KIS) 핸들러도 이 수명 의미를 따라야 백테스트=실거래 패리티가 유지된다."""
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
