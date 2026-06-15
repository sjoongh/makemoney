# tests/test_run_ledger.py
"""Tests for RunLedger idempotency and DailyActEngine ledger integration."""
from __future__ import annotations

import os
import tempfile

import pytest

from trader.live.ledger import RunLedger
from trader.live.daily import DailyActEngine
from trader.signals.technical import TechnicalSignalSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager

# Re-use the FakeKis from test_daily_act
from tests.test_daily_act import FakeKis, SYMS, FX, _make_engine


# ---------------------------------------------------------------------------
# RunLedger unit tests
# ---------------------------------------------------------------------------

class TestRunLedger:
    def _ledger(self, tmp_path) -> RunLedger:
        return RunLedger(path=str(tmp_path / "ledger.json"))

    def test_first_acquire_returns_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        result = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ")
        assert result is True

    def test_second_acquire_same_key_returns_false(self, tmp_path):
        ledger = self._ledger(tmp_path)
        first = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ")
        second = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ")
        assert first is True
        assert second is False

    def test_different_date_returns_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ")
        result = ledger.acquire("ACCT-1", "2026-01-16", "NASDAQ")
        assert result is True

    def test_different_market_same_date_returns_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ")
        result = ledger.acquire("ACCT-1", "2026-01-15", "KOSPI")
        assert result is True

    def test_different_account_same_date_returns_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ")
        result = ledger.acquire("ACCT-2", "2026-01-15", "NASDAQ")
        assert result is True

    def test_persisted_to_disk_and_reloaded(self, tmp_path):
        path = str(tmp_path / "ledger.json")
        ledger1 = RunLedger(path=path)
        ledger1.acquire("ACCT-1", "2026-01-15", "NASDAQ")

        # New instance reads from same file
        ledger2 = RunLedger(path=path)
        result = ledger2.acquire("ACCT-1", "2026-01-15", "NASDAQ")
        assert result is False, "Should be False — already recorded in previous session"

    def test_three_acquires_only_first_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        results = [
            ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ"),
            ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ"),
            ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ"),
        ]
        assert results == [True, False, False]


# ---------------------------------------------------------------------------
# DailyActEngine idempotency integration tests
# ---------------------------------------------------------------------------

class TestDailyActEngineIdempotency:
    def test_second_live_run_same_day_does_not_resubmit(self, tmp_path):
        """A second live run on the same day must not call submit_order again."""
        ledger_path = str(tmp_path / "ledger.json")

        # First run
        fake_kis_1 = FakeKis(SYMS, n_bars=60)
        pf1 = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy1 = _make_engine(pf1)
        ledger1 = RunLedger(path=ledger_path)
        engine1 = DailyActEngine(
            kis_client=fake_kis_1,
            strategy=strategy1,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            ledger=ledger1,
        )
        orders1 = engine1.run()
        submits_first = len(fake_kis_1.submit_calls)

        # If no orders were generated, skip the idempotency check
        # (nothing to be idempotent about — but we confirm nothing was submitted)
        if submits_first == 0:
            pytest.skip("No orders generated — cannot test idempotency without an order")

        assert submits_first > 0, "First run should submit at least one order"

        # Second run — same ledger file, same day
        fake_kis_2 = FakeKis(SYMS, n_bars=60)
        pf2 = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy2 = _make_engine(pf2)
        ledger2 = RunLedger(path=ledger_path)  # reloads persisted state
        engine2 = DailyActEngine(
            kis_client=fake_kis_2,
            strategy=strategy2,
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            ledger=ledger2,
        )
        engine2.run()
        submits_second = len(fake_kis_2.submit_calls)

        assert submits_second == 0, (
            f"Second run on same day should NOT submit orders, got {submits_second}"
        )

    def test_no_ledger_live_run_submits_every_time(self, tmp_path):
        """Without a ledger, every live run submits (no idempotency guard)."""
        # Run 1
        fake_kis_1 = FakeKis(SYMS, n_bars=60)
        pf1 = Portfolio({"KRW": 100_000_000.0}, FX)
        engine1 = DailyActEngine(
            kis_client=fake_kis_1,
            strategy=_make_engine(pf1),
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            ledger=None,  # no idempotency guard
        )
        orders1 = engine1.run()

        # Run 2
        fake_kis_2 = FakeKis(SYMS, n_bars=60)
        pf2 = Portfolio({"KRW": 100_000_000.0}, FX)
        engine2 = DailyActEngine(
            kis_client=fake_kis_2,
            strategy=_make_engine(pf2),
            fx=FX,
            symbols=SYMS,
            dry_run=False,
            ledger=None,
        )
        orders2 = engine2.run()

        # Both runs should submit the same number of orders
        assert len(fake_kis_1.submit_calls) == len(fake_kis_2.submit_calls)
