# trader/live/reconcile.py
"""Quantity- and position-level broker reconciliation (live safety).

The existing EOD step (`_reconcile_unfilled` in daily.py) only checks whether an
order id appears among confirmed fills — it cannot see a PARTIAL fill (ordered
100, filled 60) or an OVER-fill / DUPLICATE fill (ordered 100, filled 200).
Both are dangerous in real-money trading. This module reconciles at the
quantity level and at the position level.

Severity:
  OK         — filled == ordered (or no drift)
  WARN       — unfilled / partial (you have LESS exposure than intended — safe-ish)
  CRITICAL   — over-fill / duplicate fill, or broker-vs-internal position drift
               (you have MORE/UNINTENDED exposure — a live caller should trip the
               kill switch and alert)

Pure functions, no I/O — fully unit-testable; the live runner supplies the data.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OrderRecon:
    order_id: str
    ordered_qty: int
    filled_qty: int
    status: str    # OK | UNFILLED | PARTIAL | OVERFILLED
    severity: str  # OK | WARN | CRITICAL


@dataclass(frozen=True)
class PositionDrift:
    symbol: str
    expected_qty: int
    broker_qty: int
    diff: int          # broker - expected
    severity: str = "CRITICAL"


@dataclass
class ReconcileReport:
    orders: list[OrderRecon] = field(default_factory=list)
    drift: list[PositionDrift] = field(default_factory=list)

    @property
    def critical(self) -> list:
        return [o for o in self.orders if o.severity == "CRITICAL"] + list(self.drift)

    @property
    def warnings(self) -> list[OrderRecon]:
        return [o for o in self.orders if o.severity == "WARN"]

    @property
    def ok(self) -> bool:
        """True iff nothing CRITICAL (a live caller should kill-switch if False)."""
        return not self.critical

    def summary(self) -> str:
        n_ok = sum(1 for o in self.orders if o.severity == "OK")
        lines = [
            f"reconcile: {len(self.orders)} orders "
            f"({n_ok} ok, {len(self.warnings)} warn, "
            f"{sum(1 for o in self.orders if o.severity=='CRITICAL')} CRITICAL), "
            f"{len(self.drift)} position drift(s)"
        ]
        for o in self.orders:
            if o.severity != "OK":
                lines.append(f"  [{o.severity}] {o.order_id}: ordered {o.ordered_qty}, "
                             f"filled {o.filled_qty} → {o.status}")
        for d in self.drift:
            lines.append(f"  [CRITICAL] {d.symbol}: expected {d.expected_qty}, "
                         f"broker {d.broker_qty} (diff {d.diff:+d})")
        return "\n".join(lines)


def _qty(item) -> tuple[str, int]:
    """Accept either a dict {order_id|odno, qty} or a (order_id, qty) tuple."""
    if isinstance(item, dict):
        oid = item.get("order_id") or item.get("odno") or ""
        return str(oid), int(item.get("qty", 0) or 0)
    return str(item[0]), int(item[1])


def reconcile_orders(submitted, fills) -> list[OrderRecon]:
    """Reconcile ordered vs filled quantity per order id.

    Args:
        submitted: iterable of {order_id|odno, qty} dicts or (order_id, qty) tuples.
        fills:     iterable of fill records (e.g. KisClient.filled_orders() output);
                   multiple partial fills for one order id are summed.

    Returns one OrderRecon per submitted order, in submission order.
    """
    filled_by_id: dict[str, int] = defaultdict(int)
    for f in fills:
        oid, q = _qty(f)
        filled_by_id[oid] += q

    out: list[OrderRecon] = []
    for s in submitted:
        oid, ordered = _qty(s)
        filled = filled_by_id.get(oid, 0)
        if filled == ordered:
            status, sev = "OK", "OK"
        elif filled == 0:
            status, sev = "UNFILLED", "WARN"
        elif filled < ordered:
            status, sev = "PARTIAL", "WARN"
        else:  # filled > ordered — duplicate / over-fill
            status, sev = "OVERFILLED", "CRITICAL"
        out.append(OrderRecon(oid, ordered, filled, status, sev))
    return out


def reconcile_positions(
    expected: dict[str, int],
    broker: dict[str, int],
    *,
    ignore_zero: bool = True,
) -> list[PositionDrift]:
    """Compare internal expected positions to broker-reported positions.

    Any mismatch is CRITICAL (you hold something different from what you think).
    ``ignore_zero`` skips symbols that are 0 on both sides.
    """
    drift: list[PositionDrift] = []
    for sym in sorted(set(expected) | set(broker)):
        e = int(expected.get(sym, 0))
        b = int(broker.get(sym, 0))
        if ignore_zero and e == 0 and b == 0:
            continue
        if e != b:
            drift.append(PositionDrift(sym, e, b, b - e))
    return drift


def reconcile(submitted, fills, expected_positions=None, broker_positions=None) -> ReconcileReport:
    """Full reconciliation: order quantities + (optional) positions."""
    rep = ReconcileReport(orders=reconcile_orders(submitted, fills))
    if expected_positions is not None and broker_positions is not None:
        rep.drift = reconcile_positions(expected_positions, broker_positions)
    return rep
