# tests/test_reconcile.py
"""Tests for quantity/position broker reconciliation — live safety."""
from __future__ import annotations

from trader.live.reconcile import (
    reconcile,
    reconcile_orders,
    reconcile_positions,
)


def _sub(oid, qty):
    return {"order_id": oid, "qty": qty}


def _fill(oid, qty):
    return {"order_id": oid, "qty": qty}


# ---------------------------------------------------------------------------
# Order quantity reconciliation
# ---------------------------------------------------------------------------

def test_full_fill_is_ok():
    r = reconcile_orders([_sub("A", 100)], [_fill("A", 100)])
    assert r[0].status == "OK" and r[0].severity == "OK"


def test_unfilled_is_warn():
    r = reconcile_orders([_sub("A", 100)], [])
    assert r[0].status == "UNFILLED" and r[0].severity == "WARN"


def test_partial_fill_is_warn():
    r = reconcile_orders([_sub("A", 100)], [_fill("A", 60)])
    assert r[0].status == "PARTIAL"
    assert r[0].filled_qty == 60 and r[0].severity == "WARN"


def test_overfill_is_critical():
    # ordered 100, broker reports 200 filled → duplicate/over-fill = dangerous
    r = reconcile_orders([_sub("A", 100)], [_fill("A", 200)])
    assert r[0].status == "OVERFILLED" and r[0].severity == "CRITICAL"


def test_multiple_partial_fills_sum():
    # two partial fills for the same order id sum to a full fill
    r = reconcile_orders([_sub("A", 100)], [_fill("A", 40), _fill("A", 60)])
    assert r[0].filled_qty == 100 and r[0].status == "OK"


def test_duplicate_fill_detected_as_overfill():
    # the SAME fill arriving twice → 200 > 100 → CRITICAL
    r = reconcile_orders([_sub("A", 100)], [_fill("A", 100), _fill("A", 100)])
    assert r[0].severity == "CRITICAL"


def test_accepts_tuple_and_odno_key():
    r1 = reconcile_orders([("A", 100)], [("A", 100)])
    assert r1[0].status == "OK"
    r2 = reconcile_orders([{"odno": "A", "qty": 100}], [{"odno": "A", "qty": 50}])
    assert r2[0].status == "PARTIAL"


# ---------------------------------------------------------------------------
# Position reconciliation
# ---------------------------------------------------------------------------

def test_positions_match_no_drift():
    assert reconcile_positions({"AAPL": 10}, {"AAPL": 10}) == []


def test_position_drift_is_critical():
    d = reconcile_positions({"AAPL": 10}, {"AAPL": 7})
    assert len(d) == 1
    assert d[0].symbol == "AAPL" and d[0].diff == -3 and d[0].severity == "CRITICAL"


def test_unexpected_broker_position_flagged():
    # broker holds something internal doesn't expect at all
    d = reconcile_positions({}, {"TSLA": 5})
    assert len(d) == 1 and d[0].expected_qty == 0 and d[0].broker_qty == 5


def test_ignore_zero_both_sides():
    assert reconcile_positions({"X": 0}, {"X": 0}) == []


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------

def test_report_ok_when_clean():
    rep = reconcile([_sub("A", 100)], [_fill("A", 100)],
                    expected_positions={"AAPL": 5}, broker_positions={"AAPL": 5})
    assert rep.ok and not rep.critical


def test_report_not_ok_on_overfill():
    rep = reconcile([_sub("A", 100)], [_fill("A", 150)])
    assert not rep.ok
    assert len(rep.critical) == 1


def test_report_not_ok_on_position_drift():
    rep = reconcile([_sub("A", 100)], [_fill("A", 100)],
                    expected_positions={"AAPL": 5}, broker_positions={"AAPL": 4})
    assert not rep.ok
    assert any(getattr(c, "symbol", None) == "AAPL" for c in rep.critical)


def test_report_ok_with_only_warnings():
    # partial fill is a WARN, not CRITICAL → report still "ok" (no kill needed)
    rep = reconcile([_sub("A", 100)], [_fill("A", 60)])
    assert rep.ok
    assert len(rep.warnings) == 1
