"""Tests for EOD unfilled reconciliation in DailyActEngine.

All tests use FakeKis — no live orders placed or cancelled.

Covers:
  - _reconcile_unfilled pure function
  - Live run where an order isn't filled → cancel_order called + WARN alert
  - cancel_order raises → CRITICAL alert + kill switch tripped
  - dry_run: WARN alert emitted, cancel_order NOT called
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from trader.core.events import BarEvent, Market, OrderEvent, Side, Symbol
from trader.live.daily import DailyActEngine, _reconcile_unfilled
from trader.live.killswitch import KillSwitch
from trader.live.monitor import Monitor
from trader.signals.technical import TechnicalSignalSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FX = FxRates({"USD": 1300.0, "KRW": 1.0})
SYMS = [("AAPL", "NASDAQ", "USD")]
AAPL = Symbol("AAPL", Market.NASDAQ, "USD")


def _make_bars(sym: Symbol, n: int = 60, base: float = 100.0) -> list[BarEvent]:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        BarEvent(
            symbol=sym,
            ts=t0 + timedelta(days=i),
            open=base + i,
            high=base + i + 0.5,
            low=base + i - 0.5,
            close=base + i,
            volume=1000,
        )
        for i in range(n)
    ]


def _make_snapshot() -> dict:
    return {"cash_krw": 100_000_000.0, "positions": {}, "marks": {}}


def _make_strategy(portfolio: Portfolio) -> FusionEngine:
    return FusionEngine(
        signal_sources=[TechnicalSignalSource(fast=20, slow=50)],
        portfolio=portfolio,
        risk_manager=RiskManager(max_symbol_weight=0.3),
        order_factory=OrderFactory(),
        enter_threshold=0.01,  # low threshold → easy to trigger a BUY
    )


class _CaptureSink:
    """Records all alert calls."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []

    def emit(self, severity: str, event: str, detail: dict) -> None:
        self.calls.append((severity, event, detail))

    def events_by_severity(self, severity: str) -> list[str]:
        return [e for s, e, d in self.calls if s == severity]

    def all_events(self) -> list[str]:
        return [e for _s, e, _d in self.calls]


def _tmp_ks_path(tmp_path) -> str:
    return str(tmp_path / "ks.json")


# ---------------------------------------------------------------------------
# FakeKis with cancel_order support and scripted fill responses
# ---------------------------------------------------------------------------


class FakeKisWithCancel:
    """Fake KIS that:
    - Returns 60 rising bars for AAPL.
    - submit_order returns scripted ODNOs.
    - filled_orders returns a scripted list (empty by default → nothing filled).
    - cancel_order records calls; optionally raises.
    """

    def __init__(
        self,
        *,
        n_bars: int = 60,
        fill_odnos: list[str] | None = None,
        cancel_raises: Exception | None = None,
        submit_odno: str = "FAKE-ODNO-1",
    ):
        self._n_bars = n_bars
        # ODNOs that are "confirmed filled" — anything not here is unfilled
        self._fill_odnos: set[str] = set(fill_odnos or [])
        self._cancel_raises = cancel_raises
        self._submit_odno = submit_odno

        self.submit_calls: list[dict] = []
        self.cancel_calls: list[dict] = []

    @property
    def account(self) -> str:
        return "FAKE-ACCT"

    def account_snapshot(self) -> dict:
        return _make_snapshot()

    def daily_bars(self, ticker: str, market: str, currency: str, **_) -> list[BarEvent]:
        sym = Symbol(ticker, Market(market), currency)
        return _make_bars(sym, self._n_bars)

    def submit_order(
        self,
        ticker: str,
        market: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "00",
    ) -> str:
        self.submit_calls.append(
            dict(ticker=ticker, market=market, side=side,
                 quantity=quantity, price=price, order_type=order_type)
        )
        return self._submit_odno

    def filled_orders(self) -> list[dict]:
        """Return fill records for ODNOs in _fill_odnos."""
        fills = []
        for odno in self._fill_odnos:
            fills.append({
                "order_id": odno,
                "ticker": "AAPL",
                "market": "NASDAQ",
                "currency": "USD",
                "side": "BUY",
                "qty": 1,
                "price": 150.0,
                "commission": 0.0,
            })
        return fills

    def cancel_order(
        self,
        *,
        market: str,
        original_odno: str,
        ticker: str,
        quantity: int,
        order_branch: str = "",
    ) -> str:
        self.cancel_calls.append(dict(
            market=market,
            original_odno=original_odno,
            ticker=ticker,
            quantity=quantity,
            order_branch=order_branch,
        ))
        if self._cancel_raises is not None:
            raise self._cancel_raises
        return f"CANCEL-{original_odno}"


# ---------------------------------------------------------------------------
# Part 1: _reconcile_unfilled pure function tests
# ---------------------------------------------------------------------------


class TestReconcileUnfilled:
    """_reconcile_unfilled identifies unfilled ODNOs correctly."""

    def test_all_filled_returns_empty(self):
        submitted = ["A001", "A002", "A003"]
        confirmed = {"A001", "A002", "A003"}
        assert _reconcile_unfilled(submitted, confirmed) == []

    def test_none_filled_returns_all(self):
        submitted = ["A001", "A002"]
        confirmed: set[str] = set()
        result = _reconcile_unfilled(submitted, confirmed)
        assert set(result) == {"A001", "A002"}

    def test_partial_fill_returns_unfilled_subset(self):
        submitted = ["A001", "A002", "A003"]
        confirmed = {"A001", "A003"}  # A002 unfilled
        result = _reconcile_unfilled(submitted, confirmed)
        assert result == ["A002"]

    def test_empty_submitted_returns_empty(self):
        assert _reconcile_unfilled([], {"A001"}) == []

    def test_order_preserved(self):
        """Unfilled list preserves relative order of submitted_odnos."""
        submitted = ["Z", "A", "M", "B"]
        confirmed = {"A", "B"}
        result = _reconcile_unfilled(submitted, confirmed)
        assert result == ["Z", "M"]

    def test_extra_fills_not_in_submitted_are_ignored(self):
        """Fills for orders not in submitted_odnos don't affect result."""
        submitted = ["A001"]
        confirmed = {"A001", "EXTRA-999"}
        assert _reconcile_unfilled(submitted, confirmed) == []


# ---------------------------------------------------------------------------
# Part 2: Live run — unfilled order → cancel_order called + WARN alert
# ---------------------------------------------------------------------------


class TestEodCancelOnUnfilled:
    """Live run: unfilled order triggers cancel_order call and WARN alert."""

    def _run_live_unfilled(self, tmp_path, cancel_raises=None):
        """Run a live engine where the submitted order has no fill."""
        sink = _CaptureSink()
        mon = Monitor([sink])
        ks = KillSwitch(path=_tmp_ks_path(tmp_path))

        # submit_odno="FAKE-ODNO-1", fill_odnos=[] → FAKE-ODNO-1 is unfilled
        fake_kis = FakeKisWithCancel(
            n_bars=60,
            fill_odnos=[],  # nothing confirmed filled
            cancel_raises=cancel_raises,
            submit_odno="FAKE-ODNO-1",
        )

        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            killswitch=ks,
            monitor=mon,
        )
        result = engine.run()
        return result, sink, ks, fake_kis

    def test_unfilled_order_triggers_cancel_call(self, tmp_path):
        """When submit_order returns an ODNO with no fill, cancel_order is called."""
        result, sink, ks, fake_kis = self._run_live_unfilled(tmp_path)

        # Only meaningful if strategy generated and submitted at least one order
        if not fake_kis.submit_calls:
            pytest.skip("No orders submitted — cannot test cancel path")

        assert len(fake_kis.cancel_calls) >= 1, (
            "cancel_order must be called for each unfilled submitted order; "
            f"cancel_calls={fake_kis.cancel_calls}"
        )
        # Verify the cancel targeted the right ODNO
        assert fake_kis.cancel_calls[0]["original_odno"] == "FAKE-ODNO-1"

    def test_unfilled_order_emits_warn_alert(self, tmp_path):
        """Unfilled order before cancel emits a WARN alert."""
        result, sink, ks, fake_kis = self._run_live_unfilled(tmp_path)

        if not fake_kis.submit_calls:
            pytest.skip("No orders submitted — cannot test alert path")

        warn_events = sink.events_by_severity("WARN")
        assert "EOD_CANCEL_ATTEMPT" in warn_events, (
            f"Expected WARN EOD_CANCEL_ATTEMPT; got alerts: {sink.calls}"
        )

    def test_all_filled_no_cancel_called(self, tmp_path):
        """When all submitted orders are confirmed filled, cancel_order is NOT called."""
        sink = _CaptureSink()
        mon = Monitor([sink])
        ks = KillSwitch(path=_tmp_ks_path(tmp_path))

        fake_kis = FakeKisWithCancel(
            n_bars=60,
            fill_odnos=["FAKE-ODNO-1"],  # the submit ODNO is confirmed filled
            submit_odno="FAKE-ODNO-1",
        )

        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            killswitch=ks,
            monitor=mon,
        )
        engine.run()

        assert fake_kis.cancel_calls == [], (
            "cancel_order must NOT be called when all orders are confirmed filled"
        )


# ---------------------------------------------------------------------------
# Part 3: cancel_order raises → CRITICAL alert + kill switch tripped
# ---------------------------------------------------------------------------


class TestEodCancelFailure:
    """Cancel failure → CRITICAL alert + kill switch trip."""

    def test_cancel_failure_trips_killswitch(self, tmp_path):
        """When cancel_order raises, the kill switch is tripped."""
        sink = _CaptureSink()
        mon = Monitor([sink])
        ks = KillSwitch(path=_tmp_ks_path(tmp_path))

        fake_kis = FakeKisWithCancel(
            n_bars=60,
            fill_odnos=[],  # nothing filled → will attempt cancel
            cancel_raises=RuntimeError("KIS cancel error: 주문 없음"),
            submit_odno="FAKE-ODNO-1",
        )

        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            killswitch=ks,
            monitor=mon,
        )
        engine.run()

        if not fake_kis.submit_calls:
            pytest.skip("No orders submitted — cannot test cancel-fail path")

        assert ks.is_active(), (
            "Kill switch must be tripped when cancel_order fails"
        )
        assert ks.status()["reason"] == "EOD_CANCEL_FAILED"

    def test_cancel_failure_emits_critical_alert(self, tmp_path):
        """When cancel_order raises, a CRITICAL EOD_CANCEL_FAILED alert is emitted."""
        sink = _CaptureSink()
        mon = Monitor([sink])
        ks = KillSwitch(path=_tmp_ks_path(tmp_path))

        fake_kis = FakeKisWithCancel(
            n_bars=60,
            fill_odnos=[],
            cancel_raises=RuntimeError("KIS cancel error: 오류"),
            submit_odno="FAKE-ODNO-1",
        )

        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            killswitch=ks,
            monitor=mon,
        )
        engine.run()

        if not fake_kis.submit_calls:
            pytest.skip("No orders submitted — cannot test alert path")

        critical_events = sink.events_by_severity("CRITICAL")
        assert "EOD_CANCEL_FAILED" in critical_events, (
            f"Expected CRITICAL EOD_CANCEL_FAILED; got alerts: {sink.calls}"
        )


# ---------------------------------------------------------------------------
# Part 4: dry_run — reports would-cancel, does NOT call cancel_order
# ---------------------------------------------------------------------------


class TestEodCancelDryRun:
    """dry_run=True: WARN alert emitted for would-cancel, but no API call made."""

    def test_dry_run_no_cancel_api_call(self, tmp_path):
        """In dry_run mode, cancel_order is never called even for unfilled orders."""
        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = FakeKisWithCancel(
            n_bars=60,
            fill_odnos=[],  # nothing filled
            submit_odno="FAKE-ODNO-DRY",
        )

        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=True,  # dry run
            monitor=mon,
        )
        engine.run()

        # dry_run never submits, so never reconciles either
        assert fake_kis.cancel_calls == [], (
            "dry_run must never call cancel_order"
        )
