from __future__ import annotations
from trader.core.events import OrderEvent, FillEvent

def _row(kind, ev):
    d = {"kind": kind, "ts": ev.ts.isoformat(), "ticker": ev.symbol.ticker,
         "side": ev.side.value, "qty": ev.quantity}
    if isinstance(ev, FillEvent): d["price"] = ev.price; d["commission"] = ev.commission
    return d

class InMemoryAudit:
    """결정 재생에 충분한 순서 보존 추적. 영속 백엔드는 storage가 담당(후속)."""
    def __init__(self): self.records: list[dict] = []
    def record_order(self, o: OrderEvent) -> None: self.records.append(_row("order", o))
    def record_fill(self, f: FillEvent) -> None: self.records.append(_row("fill", f))
