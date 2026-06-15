# trader/strategy/order_factory.py
from __future__ import annotations
import math
from datetime import datetime
from uuid import uuid4
from trader.core.events import OrderEvent, Side, TargetPosition
from trader.strategy.portfolio import Portfolio

class OrderFactory:
    """목표비중 → 정수 주식 델타. 가격은 해당 통화, equity는 KRW 기준으로 환산해 사이징."""
    def orders_for_target(self, target: TargetPosition, portfolio: Portfolio,
                          price: float, ts: datetime) -> list[OrderEvent]:
        sym = target.symbol
        price_krw = portfolio.fx.to_krw(price, sym.currency)
        if price_krw <= 0: return []
        target_value_krw = target.target_weight * portfolio.equity_krw()
        target_qty = int(math.floor(target_value_krw / price_krw))
        delta = target_qty - portfolio.position(sym)
        if delta == 0: return []
        side = Side.BUY if delta > 0 else Side.SELL
        return [OrderEvent(uuid4(), sym, ts, side, abs(delta), reason=target.reason)]
