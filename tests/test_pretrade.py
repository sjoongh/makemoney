# tests/test_pretrade.py
"""Tests for PreTradeRiskGate, RunCircuitBreaker, and DailyActEngine wiring."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from trader.core.events import BarEvent, Market, OrderEvent, Side, Symbol
from trader.live.pretrade import (
    GateResult,
    PreTradeLimits,
    PreTradeRiskGate,
    RunCircuitBreaker,
)
from trader.strategy.portfolio import FxRates, Portfolio

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FX = FxRates({"USD": 1300.0, "KRW": 1.0})
LIMITS = PreTradeLimits(
    max_order_notional_krw=5_000_000,
    max_position_weight=0.30,
    max_orders_per_run=10,
    fat_finger_qty=10_000,
    price_sanity_pct=0.30,
    cash_buffer_pct=0.01,
)
AAPL = Symbol("AAPL", Market.NASDAQ, "USD")
SAMSUNG = Symbol("005930", Market.KOSPI, "KRW")

TS = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _order(symbol=AAPL, side=Side.BUY, qty=10) -> OrderEvent:
    """Create a minimal valid OrderEvent."""
    return OrderEvent(
        order_id=uuid4(),
        symbol=symbol,
        ts=TS,
        side=side,
        quantity=qty,
    )


def _portfolio(cash_krw: float = 100_000_000.0) -> Portfolio:
    """Empty portfolio with given KRW cash."""
    return Portfolio({"KRW": cash_krw}, FX)


def _gate(limits: PreTradeLimits = LIMITS) -> PreTradeRiskGate:
    return PreTradeRiskGate(limits, FX)


# ---------------------------------------------------------------------------
# PreTradeRiskGate — individual block reasons
# ---------------------------------------------------------------------------


class TestPreTradeGateBlockReasons:

    def test_normal_order_approves(self):
        """A well-formed small order with ample cash should pass all checks."""
        gate = _gate()
        pf = _portfolio(cash_krw=100_000_000.0)
        order = _order(qty=10)
        result = gate.check_order(order, decision_price=100.0, last_close=100.0, portfolio=pf)
        assert result.approved is True
        assert result.reason == ""

    def test_fat_finger_qty_too_large(self):
        """Quantity exceeding fat_finger_qty is blocked with FAT_FINGER_QTY."""
        gate = _gate()
        pf = _portfolio()
        order = _order(qty=LIMITS.fat_finger_qty + 1)
        result = gate.check_order(order, decision_price=1.0, last_close=1.0, portfolio=pf)
        assert result.approved is False
        assert result.reason == "FAT_FINGER_QTY"

    def test_fat_finger_exactly_at_limit_is_ok(self):
        """Quantity exactly equal to fat_finger_qty should pass the fat-finger check."""
        gate = _gate()
        pf = _portfolio()
        # fat_finger_qty=10_000, notional = 10000*1 USD = 13_000_000 KRW > max_order_notional
        # so this will hit MAX_ORDER_NOTIONAL — but NOT FAT_FINGER_QTY
        order = _order(qty=LIMITS.fat_finger_qty)
        result = gate.check_order(order, decision_price=1.0, last_close=1.0, portfolio=pf)
        assert result.reason != "FAT_FINGER_QTY"

    def test_price_sanity_last_close_zero(self):
        """last_close <= 0 triggers PRICE_SANITY."""
        gate = _gate()
        pf = _portfolio()
        order = _order(qty=1)
        result = gate.check_order(order, decision_price=100.0, last_close=0.0, portfolio=pf)
        assert result.approved is False
        assert result.reason == "PRICE_SANITY"

    def test_price_sanity_deviation_too_large(self):
        """decision_price deviating >30% from last_close triggers PRICE_SANITY."""
        gate = _gate()
        pf = _portfolio()
        order = _order(qty=1)
        # 31% deviation above last_close
        result = gate.check_order(order, decision_price=131.0, last_close=100.0, portfolio=pf)
        assert result.approved is False
        assert result.reason == "PRICE_SANITY"

    def test_price_sanity_deviation_at_boundary_passes(self):
        """Deviation clearly below price_sanity_pct (30%) is not blocked for price sanity."""
        gate = _gate()
        pf = _portfolio()
        order = _order(qty=1)
        # 29% deviation — well inside the 30% threshold, should not fire PRICE_SANITY
        result = gate.check_order(order, decision_price=129.0, last_close=100.0, portfolio=pf)
        # May hit other checks, but NOT PRICE_SANITY
        assert result.reason != "PRICE_SANITY"

    def test_max_order_notional_krw_exceeded(self):
        """Order notional exceeding max_order_notional_krw is blocked."""
        gate = _gate()
        pf = _portfolio(cash_krw=500_000_000.0)
        # 10 shares * $400 * 1300 = 5,200,000 KRW > 5,000,000 cap
        order = _order(qty=10)
        result = gate.check_order(order, decision_price=400.0, last_close=400.0, portfolio=pf)
        assert result.approved is False
        assert result.reason == "MAX_ORDER_NOTIONAL"

    def test_insufficient_cash_buy(self):
        """BUY order where notional*(1+buffer) > cash triggers INSUFFICIENT_CASH."""
        gate = _gate()
        # Order: 10 shares * $100 * 1300 = 1,300,000 KRW
        # With 1% buffer: 1,313,000 KRW needed
        # Cash: only 1,000,000 KRW
        pf = _portfolio(cash_krw=1_000_000.0)
        order = _order(qty=10)
        result = gate.check_order(order, decision_price=100.0, last_close=100.0, portfolio=pf)
        assert result.approved is False
        assert result.reason == "INSUFFICIENT_CASH"

    def test_insufficient_cash_does_not_apply_to_sell(self):
        """SELL orders skip the cash check (risk-reducing)."""
        gate = _gate()
        pf = _portfolio(cash_krw=0.0)   # zero cash
        order = _order(side=Side.SELL, qty=1)
        result = gate.check_order(order, decision_price=100.0, last_close=100.0, portfolio=pf)
        # Should not block on INSUFFICIENT_CASH
        assert result.reason != "INSUFFICIENT_CASH"

    def test_max_position_weight_exceeded(self):
        """BUY that would push position weight above max_position_weight is blocked."""
        limits = PreTradeLimits(
            max_order_notional_krw=500_000_000,   # very high notional cap — won't fire
            max_position_weight=0.30,
            max_orders_per_run=10,
            fat_finger_qty=10_000,
            price_sanity_pct=0.30,
            cash_buffer_pct=0.01,
        )
        gate = PreTradeRiskGate(limits, FX)
        # 200 shares * $100 * 1300 KRW/USD = 26,000,000 KRW notional
        # equity = 50,000,000 KRW cash (no positions)
        # post-trade weight = 26,000,000 / 50,000,000 = 0.52 > 0.30 → blocked
        # cash check: 26,000,000 * 1.01 = 26,260,000 < 50,000,000 → passes
        pf = _portfolio(cash_krw=50_000_000.0)
        order = _order(qty=200)
        result = gate.check_order(order, decision_price=100.0, last_close=100.0, portfolio=pf)
        assert result.approved is False
        assert result.reason == "MAX_POSITION_WEIGHT"

    def test_max_position_weight_does_not_apply_to_sell(self):
        """SELL orders skip the position weight check."""
        limits = PreTradeLimits(
            max_order_notional_krw=500_000_000,
            max_position_weight=0.01,    # extremely tight cap
            max_orders_per_run=10,
            fat_finger_qty=10_000,
            price_sanity_pct=0.30,
            cash_buffer_pct=0.01,
        )
        gate = PreTradeRiskGate(limits, FX)
        pf = _portfolio(cash_krw=100_000_000.0)
        order = _order(side=Side.SELL, qty=1)
        result = gate.check_order(order, decision_price=100.0, last_close=100.0, portfolio=pf)
        assert result.reason != "MAX_POSITION_WEIGHT"

    def test_sell_passes_with_fat_finger_and_price_ok(self):
        """SELL with valid qty and price passes (skips cash/weight checks)."""
        gate = _gate()
        pf = _portfolio(cash_krw=0.0)
        order = _order(side=Side.SELL, qty=5)
        result = gate.check_order(order, decision_price=100.0, last_close=100.0, portfolio=pf)
        assert result.approved is True

    def test_check_order_order_of_checks_fat_finger_first(self):
        """FAT_FINGER_QTY is reported even when price is also bad."""
        gate = _gate()
        pf = _portfolio()
        order = _order(qty=99_999)      # fat finger
        # also a bad price (500% deviation) — but fat finger fires first
        result = gate.check_order(order, decision_price=600.0, last_close=100.0, portfolio=pf)
        assert result.reason == "FAT_FINGER_QTY"

    def test_krw_symbol_uses_krw_fx(self):
        """KRW-denominated symbol uses fx.to_krw correctly (rate=1.0)."""
        gate = _gate()
        pf = _portfolio(cash_krw=100_000_000.0)
        order = _order(symbol=SAMSUNG, qty=10)
        # 10 * 50000 KRW = 500,000 KRW notional — well within 5M cap
        result = gate.check_order(order, decision_price=50_000.0, last_close=50_000.0, portfolio=pf)
        assert result.approved is True


# ---------------------------------------------------------------------------
# RunCircuitBreaker
# ---------------------------------------------------------------------------


class TestRunCircuitBreaker:

    def test_allows_up_to_max(self):
        """allow() returns True for the first max_orders_per_run calls."""
        breaker = RunCircuitBreaker(max_orders_per_run=3)
        assert breaker.allow() is True   # 1
        assert breaker.allow() is True   # 2
        assert breaker.allow() is True   # 3

    def test_blocks_after_max(self):
        """allow() returns False once the cap is reached."""
        breaker = RunCircuitBreaker(max_orders_per_run=3)
        for _ in range(3):
            breaker.allow()
        assert breaker.allow() is False
        assert breaker.allow() is False   # stays blocked

    def test_count_tracks_approved(self):
        """count reflects the number of approved (True) calls."""
        breaker = RunCircuitBreaker(max_orders_per_run=5)
        for _ in range(3):
            breaker.allow()
        assert breaker.count == 3

    def test_count_does_not_increment_after_cap(self):
        """count stops incrementing once cap is hit."""
        breaker = RunCircuitBreaker(max_orders_per_run=2)
        breaker.allow(); breaker.allow()
        breaker.allow()   # blocked — should not increment
        assert breaker.count == 2

    def test_zero_cap_blocks_immediately(self):
        """max_orders_per_run=0 blocks the very first call."""
        breaker = RunCircuitBreaker(max_orders_per_run=0)
        assert breaker.allow() is False

    def test_large_cap_allows_many(self):
        breaker = RunCircuitBreaker(max_orders_per_run=100)
        for _ in range(100):
            assert breaker.allow() is True
        assert breaker.allow() is False


# ---------------------------------------------------------------------------
# DailyActEngine wiring — FakeKis integration tests
# ---------------------------------------------------------------------------

from trader.live.daily import DailyActEngine, protective_limit_price
from trader.signals.technical import TechnicalSignalSource
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.risk import RiskManager


def _make_bars(sym: Symbol, n: int = 60, base: float = 100.0) -> list[BarEvent]:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = []
    for i in range(n):
        close = base + i
        bars.append(
            BarEvent(
                symbol=sym, ts=t0 + timedelta(days=i),
                open=close, high=close + 0.5, low=close - 0.5,
                close=close, volume=1000,
            )
        )
    return bars


def _make_snapshot() -> dict:
    return {"cash_krw": 100_000_000.0, "positions": {}, "marks": {}}


class FakeKis:
    def __init__(self, symbols, n_bars=60):
        self._symbols = symbols
        self._n_bars = n_bars
        self.submit_calls: list[dict] = []

    @property
    def account(self) -> str:
        return "FAKE-ACCT"

    def account_snapshot(self) -> dict:
        return _make_snapshot()

    def daily_bars(self, ticker, market, currency, **_):
        sym = Symbol(ticker, Market(market), currency)
        return _make_bars(sym, self._n_bars)

    def submit_order(self, ticker, market, side, quantity, price=0.0, order_type="00"):
        self.submit_calls.append(
            dict(ticker=ticker, market=market, side=side,
                 quantity=quantity, price=price, order_type=order_type)
        )
        return f"FAKE-{len(self.submit_calls)}"


SYMS = [("AAPL", "NASDAQ", "USD")]


def _fusion(pf: Portfolio) -> FusionEngine:
    return FusionEngine(
        signal_sources=[TechnicalSignalSource(fast=20, slow=50)],
        portfolio=pf,
        risk_manager=RiskManager(max_symbol_weight=0.3),
        order_factory=OrderFactory(),
        enter_threshold=0.01,
    )


class TestDailyActEngineGateWiring:

    def test_order_exceeding_notional_cap_not_submitted(self):
        """An order whose notional exceeds the cap is blocked — FakeKis.submit not called."""
        fake_kis = FakeKis(SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _fusion(pf)

        # Set notional cap to 1 KRW — every real order will be blocked
        tight_limits = PreTradeLimits(
            max_order_notional_krw=1.0,   # impossibly tight
            max_position_weight=0.30,
            max_orders_per_run=10,
            fat_finger_qty=10_000,
            price_sanity_pct=0.30,
            cash_buffer_pct=0.01,
        )
        gate = PreTradeRiskGate(tight_limits, FX)
        breaker = RunCircuitBreaker(max_orders_per_run=10)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            band=0.01,
            dry_run=False,
            gate=gate,
            breaker=breaker,
        )

        submitted = engine.run()

        # No orders submitted through KIS
        assert fake_kis.submit_calls == [], (
            f"Expected no submit_order calls with 1 KRW notional cap; got {fake_kis.submit_calls}"
        )
        # Blocked orders recorded on engine
        assert len(engine.blocked) > 0, "Expected at least one blocked order recorded"
        assert all(b["reason"] == "MAX_ORDER_NOTIONAL" for b in engine.blocked)

    def test_normal_order_is_submitted(self):
        """An order within all limits IS submitted to KIS."""
        fake_kis = FakeKis(SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _fusion(pf)

        # Generous limits — everything should pass
        generous_limits = PreTradeLimits(
            max_order_notional_krw=500_000_000,
            max_position_weight=0.99,
            max_orders_per_run=10,
            fat_finger_qty=10_000,
            price_sanity_pct=0.30,
            cash_buffer_pct=0.01,
        )
        gate = PreTradeRiskGate(generous_limits, FX)
        breaker = RunCircuitBreaker(max_orders_per_run=10)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            band=0.01,
            dry_run=False,
            gate=gate,
            breaker=breaker,
        )

        submitted = engine.run()

        assert len(fake_kis.submit_calls) > 0, (
            "Expected at least one submit_order call with generous limits"
        )
        assert len(engine.blocked) == 0, "Expected no blocked orders with generous limits"

    def test_circuit_breaker_prevents_excess_submissions(self):
        """Circuit breaker with cap=0 blocks all submissions."""
        fake_kis = FakeKis(SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _fusion(pf)

        generous_limits = PreTradeLimits(
            max_order_notional_krw=500_000_000,
            max_position_weight=0.99,
            max_orders_per_run=0,   # cap=0 — circuit immediately trips
            fat_finger_qty=10_000,
            price_sanity_pct=0.30,
            cash_buffer_pct=0.01,
        )
        gate = PreTradeRiskGate(generous_limits, FX)
        breaker = RunCircuitBreaker(max_orders_per_run=0)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            band=0.01,
            dry_run=False,
            gate=gate,
            breaker=breaker,
        )

        engine.run()

        assert fake_kis.submit_calls == [], "Circuit breaker cap=0 must block all submissions"
        breaker_blocks = [b for b in engine.blocked if b["reason"] == "CIRCUIT_BREAKER"]
        assert len(breaker_blocks) > 0, "Expected CIRCUIT_BREAKER entries in engine.blocked"

    def test_dry_run_still_returns_orders_without_submission(self):
        """In dry_run mode, the gate runs informally but orders are still returned."""
        fake_kis = FakeKis(SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _fusion(pf)

        tight_limits = PreTradeLimits(max_order_notional_krw=1.0)
        gate = PreTradeRiskGate(tight_limits, FX)
        breaker = RunCircuitBreaker(max_orders_per_run=10)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=True,   # dry run
            gate=gate,
            breaker=breaker,
        )

        orders = engine.run()

        # dry_run returns all orders regardless of gate result
        assert isinstance(orders, list)
        # submit never called
        assert fake_kis.submit_calls == []

    def test_default_gate_and_breaker_are_none_for_backward_compat(self):
        """DailyActEngine leaves gate/breaker as None when not supplied (backward-compat)."""
        fake_kis = FakeKis(SYMS, n_bars=60)
        pf = Portfolio({"KRW": 100_000_000.0}, FX)
        strategy = _fusion(pf)

        engine = DailyActEngine(
            kis_client=fake_kis,
            strategy=strategy,
            fx=FX,
            symbols=SYMS,
            dry_run=True,
        )

        # Not supplied → None (opt-in design)
        assert engine.gate is None
        assert engine.breaker is None
        # run should not crash
        engine.run()
