# tests/test_audit.py
from datetime import datetime, timezone
from uuid import uuid4
from trader.core.events import Symbol, Market, OrderEvent, FillEvent, Side
from trader.observability.audit import InMemoryAudit

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _t(): return datetime(2026,1,3,tzinfo=timezone.utc)

def test_audit_records_orders_and_fills_in_order():
    a = InMemoryAudit()
    a.record_order(OrderEvent(uuid4(), SYM, _t(), Side.BUY, 5))
    a.record_fill(FillEvent(uuid4(), SYM, _t(), Side.BUY, 5, 10.0, 0.0, "USD"))
    kinds = [r["kind"] for r in a.records]
    assert kinds == ["order", "fill"]
