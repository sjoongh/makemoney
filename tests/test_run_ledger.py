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
        result = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")
        assert result is True

    def test_second_acquire_same_key_returns_false(self, tmp_path):
        ledger = self._ledger(tmp_path)
        first = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")
        second = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")
        assert first is True
        assert second is False

    def test_different_ticker_same_market_date_both_return_true(self, tmp_path):
        """Two different tickers in the same market+date must both acquire independently."""
        ledger = self._ledger(tmp_path)
        result_aapl = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")
        result_nvda = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "NVDA")
        assert result_aapl is True
        assert result_nvda is True

    def test_same_ticker_twice_true_then_false(self, tmp_path):
        """Same ticker twice: first call True, second call False."""
        ledger = self._ledger(tmp_path)
        first = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "MSFT")
        second = ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "MSFT")
        assert first is True
        assert second is False

    def test_different_date_returns_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")
        result = ledger.acquire("ACCT-1", "2026-01-16", "NASDAQ", "AAPL")
        assert result is True

    def test_different_market_same_date_returns_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")
        result = ledger.acquire("ACCT-1", "2026-01-15", "KOSPI", "AAPL")
        assert result is True

    def test_different_account_same_date_returns_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")
        result = ledger.acquire("ACCT-2", "2026-01-15", "NASDAQ", "AAPL")
        assert result is True

    def test_persisted_to_disk_and_reloaded(self, tmp_path):
        path = str(tmp_path / "ledger.json")
        ledger1 = RunLedger(path=path)
        ledger1.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")

        # New instance reads from same file
        ledger2 = RunLedger(path=path)
        result = ledger2.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")
        assert result is False, "Should be False — already recorded in previous session"

    def test_three_acquires_only_first_true(self, tmp_path):
        ledger = self._ledger(tmp_path)
        results = [
            ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL"),
            ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL"),
            ledger.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL"),
        ]
        assert results == [True, False, False]

    def test_multiple_tickers_independent_across_reloads(self, tmp_path):
        """Persist AAPL submission; reload; NVDA still acquires True, AAPL False."""
        path = str(tmp_path / "ledger.json")
        ledger1 = RunLedger(path=path)
        ledger1.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL")

        ledger2 = RunLedger(path=path)
        assert ledger2.acquire("ACCT-1", "2026-01-15", "NASDAQ", "NVDA") is True
        assert ledger2.acquire("ACCT-1", "2026-01-15", "NASDAQ", "AAPL") is False


# ---------------------------------------------------------------------------
# DailyActEngine idempotency integration tests
# ---------------------------------------------------------------------------

# Two-symbol NASDAQ list for multi-ticker tests
TWO_SYMS = [("AAPL", "NASDAQ", "USD"), ("MSFT", "NASDAQ", "USD")]


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

    def test_two_nasdaq_symbols_both_submit_on_first_run(self, tmp_path):
        """Two NASDAQ symbols must each submit independently (ticker-scoped ledger)."""
        ledger_path = str(tmp_path / "ledger.json")

        fake_kis = FakeKis(TWO_SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _make_engine(pf)
        ledger = RunLedger(path=ledger_path)
        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=TWO_SYMS,
            dry_run=False,
            ledger=ledger,
        )
        orders = engine.run()

        # Both symbols must be able to submit — no symbol blocks the other
        submitted_tickers = {c["ticker"] for c in fake_kis.submit_calls}
        order_tickers = {o.symbol.ticker for o in orders}

        # Every order that was generated must have been submitted
        # (no second ticker blocked by first ticker's ledger entry)
        assert submitted_tickers == order_tickers, (
            f"All order tickers should be submitted. "
            f"Orders: {order_tickers}, Submitted: {submitted_tickers}"
        )

    def test_same_day_rerun_submits_neither_symbol(self, tmp_path):
        """After a full run with two symbols, re-run submits neither."""
        ledger_path = str(tmp_path / "ledger.json")

        # First run
        fake_kis_1 = FakeKis(TWO_SYMS, n_bars=60)
        pf1 = Portfolio({"KRW": 100_000_000.0}, FX)
        ledger1 = RunLedger(path=ledger_path)
        engine1 = DailyActEngine(
            kis_client=fake_kis_1,
            strategy=_make_engine(pf1),
            fx=FX,
            symbols=TWO_SYMS,
            dry_run=False,
            ledger=ledger1,
        )
        engine1.run()
        if len(fake_kis_1.submit_calls) == 0:
            pytest.skip("No orders generated — cannot test rerun idempotency")

        # Second run — same ledger
        fake_kis_2 = FakeKis(TWO_SYMS, n_bars=60)
        pf2 = Portfolio({"KRW": 100_000_000.0}, FX)
        ledger2 = RunLedger(path=ledger_path)
        engine2 = DailyActEngine(
            kis_client=fake_kis_2,
            strategy=_make_engine(pf2),
            fx=FX,
            symbols=TWO_SYMS,
            dry_run=False,
            ledger=ledger2,
        )
        engine2.run()

        assert len(fake_kis_2.submit_calls) == 0, (
            f"Re-run must submit nothing for already-recorded tickers, "
            f"got {fake_kis_2.submit_calls}"
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
