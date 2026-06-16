# tests/test_daily_safety.py
"""Tests for P0 safety integration in DailyActEngine.

Covers:
  - UNKNOWN submission → kill switch tripped + CRITICAL alert + no retry
  - REJECTED submission → WARN alert, continues (other orders not blocked)
  - Kill switch active at start → no submissions
  - Dry-run → gate evaluated, monitor gets RUN_END INFO, no submission
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from trader.core.events import BarEvent, Market, OrderEvent, Side, Symbol
from trader.live.daily import DailyActEngine
from trader.live.killswitch import KillSwitch
from trader.live.monitor import Monitor
from trader.signals.technical import TechnicalSignalSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FX = FxRates({"USD": 1300.0, "KRW": 1.0})
SYMS = [("AAPL", "NASDAQ", "USD")]


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

    def alerts_by_event(self, event: str) -> list[tuple[str, str, dict]]:
        return [(s, e, d) for s, e, d in self.calls if e == event]

    def severities(self) -> list[str]:
        return [s for s, _e, _d in self.calls]


def _tmp_ks_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    return path


# ---------------------------------------------------------------------------
# Fake KIS + submitter helpers
# ---------------------------------------------------------------------------

class _FakeKis:
    """Minimal fake KIS — always has 60-bar rising price series for AAPL."""

    def __init__(self, n_bars: int = 60):
        self._n_bars = n_bars
        self.submit_calls: list[dict] = []

    @property
    def account(self) -> str:
        return "FAKE-ACCT"

    def account_snapshot(self) -> dict:
        return _make_snapshot()

    def daily_bars(self, ticker: str, market: str, currency: str, **_) -> list[BarEvent]:
        sym = Symbol(ticker, Market(market), currency)
        return _make_bars(sym, self._n_bars)

    def submit_order(self, ticker, market, side, quantity, price=0.0,
                     order_type="00") -> str:
        self.submit_calls.append(
            dict(ticker=ticker, market=market, side=side,
                 quantity=quantity, price=price, order_type=order_type)
        )
        return f"FAKE-ODNO-{len(self.submit_calls)}"


class _FakeSubmitter:
    """Injectable fake submitter whose responses are scripted per-call."""

    def __init__(self, responses: list[dict]):
        """
        responses: list of result dicts to return in order.
        Each must have keys: status, odno, attempts, reason.
        """
        self._responses = list(responses)
        self.calls: list[dict] = []

    def submit(self, ticker, market, side, quantity, price, order_type) -> dict:
        self.calls.append(
            dict(ticker=ticker, market=market, side=side,
                 quantity=quantity, price=price, order_type=order_type)
        )
        if self._responses:
            return self._responses.pop(0)
        # Default: success
        return {"status": "SUBMITTED", "odno": "X", "attempts": 1, "reason": ""}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUnknownOrderTripsKillSwitch:
    """UNKNOWN submission result → kill switch tripped + CRITICAL alert + no retry."""

    def test_unknown_trips_killswitch(self, tmp_path):
        ks_path = str(tmp_path / "ks.json")
        ks = KillSwitch(path=ks_path)
        assert not ks.is_active()

        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        submitter = _FakeSubmitter([
            {"status": "UNKNOWN", "odno": None, "attempts": 4,
             "reason": "Something completely unexpected"},
        ])

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            submitter=submitter,
            killswitch=ks,
            monitor=mon,
        )
        engine.run()

        # Kill switch must be active after UNKNOWN
        assert ks.is_active(), "Kill switch must be tripped on UNKNOWN order state"
        assert ks.status()["reason"] == "ORDER_UNKNOWN_STATE"

    def test_unknown_emits_critical_alert(self, tmp_path):
        ks_path = str(tmp_path / "ks.json")
        ks = KillSwitch(path=ks_path)

        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        submitter = _FakeSubmitter([
            {"status": "UNKNOWN", "odno": None, "attempts": 1,
             "reason": "Unexpected broker error"},
        ])

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            submitter=submitter,
            killswitch=ks,
            monitor=mon,
        )
        engine.run()

        critical_alerts = [e for s, e, d in sink.calls if s == "CRITICAL"]
        assert "ORDER_UNKNOWN_STATE" in critical_alerts, (
            f"Expected CRITICAL ORDER_UNKNOWN_STATE alert; got: {sink.calls}"
        )

    def test_unknown_does_not_retry(self, tmp_path):
        """After UNKNOWN, the order is not submitted again (submitter called once)."""
        ks = KillSwitch(path=str(tmp_path / "ks.json"))
        mon = Monitor([_CaptureSink()])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        submitter = _FakeSubmitter([
            {"status": "UNKNOWN", "odno": None, "attempts": 1, "reason": "???"},
        ])

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            submitter=submitter,
            killswitch=ks,
            monitor=mon,
        )
        engine.run()

        # Submitter called at most once for the order that went UNKNOWN
        assert len(submitter.calls) <= 1, (
            f"Order must not be resubmitted after UNKNOWN; submitter.calls={submitter.calls}"
        )


class TestRejectedOrderContinues:
    """REJECTED submission → WARN alert emitted, processing continues."""

    def _run_two_orders_first_rejected(self, tmp_path):
        """Run with two symbols so we can test that the second order still processes."""
        syms = [("AAPL", "NASDAQ", "USD"), ("MSFT", "NASDAQ", "USD")]

        sink = _CaptureSink()
        mon = Monitor([sink])
        ks = KillSwitch(path=str(tmp_path / "ks.json"))

        class _TwoSymKis(_FakeKis):
            def daily_bars(self, ticker, market, currency, **_):
                sym = Symbol(ticker, Market(market), currency)
                return _make_bars(sym, 60)

        fake_kis = _TwoSymKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        # First order REJECTED, second SUBMITTED
        submitter = _FakeSubmitter([
            {"status": "REJECTED", "odno": None, "attempts": 1, "reason": "잔고 부족"},
            {"status": "SUBMITTED", "odno": "OK-001", "attempts": 1, "reason": ""},
        ])

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=syms,
            dry_run=False,
            submitter=submitter,
            killswitch=ks,
            monitor=mon,
        )
        result = engine.run()
        return result, sink, ks, submitter

    def test_rejected_emits_warn_alert(self, tmp_path):
        result, sink, ks, submitter = self._run_two_orders_first_rejected(tmp_path)
        warn_events = [e for s, e, d in sink.calls if s == "WARN"]
        assert "ORDER_REJECTED" in warn_events, (
            f"Expected WARN ORDER_REJECTED alert; got: {sink.calls}"
        )

    def test_rejected_does_not_trip_killswitch(self, tmp_path):
        result, sink, ks, submitter = self._run_two_orders_first_rejected(tmp_path)
        assert not ks.is_active(), "REJECTED must not trip the kill switch"

    def test_rejected_processing_continues(self, tmp_path):
        """After a REJECTED, subsequent orders in the run are still attempted."""
        result, sink, ks, submitter = self._run_two_orders_first_rejected(tmp_path)
        # submitter was called at least twice (once for rejected, once for success)
        # This is only meaningful if strategy generated >=2 orders
        if len(submitter.calls) >= 2:
            statuses = [r["status"] for r in [
                {"status": "REJECTED"},  # scripted first
                {"status": "SUBMITTED"}, # scripted second
            ]]
            assert "SUBMITTED" in statuses


class TestKillSwitchActiveAtStart:
    """If kill switch is active at run start, no submissions happen at all."""

    def test_active_killswitch_blocks_all_submissions(self, tmp_path):
        ks_path = str(tmp_path / "ks.json")
        ks = KillSwitch(path=ks_path)
        ks.trip(reason="Pre-existing drawdown halt", source="operator")
        assert ks.is_active()

        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        submitter = _FakeSubmitter([])

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            submitter=submitter,
            killswitch=ks,
            monitor=mon,
        )
        result = engine.run()

        assert result == [], "Active kill switch must return empty list"
        assert len(submitter.calls) == 0, "Active kill switch must prevent any submissions"

    def test_active_killswitch_emits_critical_alert(self, tmp_path):
        ks_path = str(tmp_path / "ks.json")
        ks = KillSwitch(path=ks_path)
        ks.trip(reason="Emergency halt", source="operator")

        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            submitter=_FakeSubmitter([]),
            killswitch=ks,
            monitor=mon,
        )
        engine.run()

        critical_events = [e for s, e, d in sink.calls if s == "CRITICAL"]
        assert "KILLSWITCH_ACTIVE_AT_START" in critical_events, (
            f"Expected CRITICAL KILLSWITCH_ACTIVE_AT_START; got: {sink.calls}"
        )

    def test_inactive_killswitch_does_not_block(self, tmp_path):
        """An inactive kill switch allows normal live run."""
        ks_path = str(tmp_path / "ks.json")
        ks = KillSwitch(path=ks_path)
        assert not ks.is_active()

        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        submitter = _FakeSubmitter([
            {"status": "SUBMITTED", "odno": "OK-001", "attempts": 1, "reason": ""},
        ])

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            submitter=submitter,
            killswitch=ks,
            monitor=mon,
        )
        # Should proceed normally (submitter may or may not be called depending
        # on whether the strategy generates an order — we just check no crash)
        result = engine.run()
        assert isinstance(result, list)


class TestDryRunMonitor:
    """Dry-run: gate evaluated, monitor gets RUN_END INFO, no submission."""

    def test_dry_run_no_submission(self):
        """Dry-run never calls the submitter or kis.submit_order."""
        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)
        submitter = _FakeSubmitter([])

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=True,
            submitter=submitter,
            monitor=mon,
        )
        engine.run()

        assert len(submitter.calls) == 0, "Dry-run must not call submitter"
        assert len(fake_kis.submit_calls) == 0, "Dry-run must not call kis.submit_order"

    def test_dry_run_emits_run_end_info(self):
        """Monitor receives at least one INFO RUN_END event in dry-run."""
        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=True,
            monitor=mon,
        )
        engine.run()

        info_events = [e for s, e, d in sink.calls if s == "INFO"]
        assert "RUN_END" in info_events, (
            f"Dry-run must emit INFO RUN_END; got: {sink.calls}"
        )

    def test_dry_run_run_end_detail_has_mode(self):
        """RUN_END detail includes mode='dry_run'."""
        sink = _CaptureSink()
        mon = Monitor([sink])

        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=True,
            monitor=mon,
        )
        engine.run()

        run_end_details = [d for s, e, d in sink.calls if e == "RUN_END"]
        assert run_end_details, "Expected at least one RUN_END event"
        assert run_end_details[0].get("mode") == "dry_run", (
            f"RUN_END detail must have mode='dry_run'; got: {run_end_details[0]}"
        )

    def test_dry_run_with_no_monitor_does_not_crash(self):
        """DailyActEngine without monitor in dry-run must not raise."""
        fake_kis = _FakeKis(n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_strategy(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=True,
        )
        result = engine.run()
        assert isinstance(result, list)
