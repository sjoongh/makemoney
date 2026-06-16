# tests/test_slippage.py
"""Tests for SlippageModel, tradable(), and SimulatedExecutionHandler slippage integration.

All hand-verified formulas:
  slippage = notional * (spread_bps + open_close_extra_bps) / 10_000
  notional = price * quantity

KOSPI defaults: spread_bps=8.0, open_close_extra_bps=5.0
NASDAQ defaults: spread_bps=3.0, open_close_extra_bps=5.0
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from trader.core.events import BarEvent, Market, OrderEvent, Side, Symbol
from trader.execution.costs import (
    DEFAULT_SLIPPAGE_BPS,
    SlippageModel,
    tradable,
)
from trader.execution.simulated import SimulatedExecutionHandler
from trader.execution.costs import BpsCostModel


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

KOSPI_SYM = Symbol("005930", Market.KOSPI, "KRW")   # Samsung
NASDAQ_SYM = Symbol("AAPL", Market.NASDAQ, "USD")

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _bar(sym: Symbol, open_: float, volume: int = 1000, day: int = 1) -> BarEvent:
    ts = T0 + timedelta(days=day)
    return BarEvent(sym, ts, open=open_, high=open_ + 1, low=open_ - 1,
                    close=open_, volume=volume)


def _order(sym: Symbol, side: Side = Side.BUY, qty: int = 10) -> OrderEvent:
    return OrderEvent(uuid4(), sym, T0, side, qty)


# ---------------------------------------------------------------------------
# SlippageModel — disabled (default)
# ---------------------------------------------------------------------------

class TestSlippageModelDisabled:
    def test_default_enabled_is_false(self):
        m = SlippageModel()
        assert m.enabled is False

    def test_disabled_returns_zero_kospi_buy(self):
        m = SlippageModel()
        assert m.slippage(70_000.0, 10, Market.KOSPI, Side.BUY) == 0.0

    def test_disabled_returns_zero_kospi_sell(self):
        m = SlippageModel()
        assert m.slippage(70_000.0, 10, Market.KOSPI, Side.SELL) == 0.0

    def test_disabled_returns_zero_nasdaq(self):
        m = SlippageModel()
        assert m.slippage(200.0, 50, Market.NASDAQ, Side.BUY) == 0.0

    def test_disabled_returns_zero_regardless_of_at_open(self):
        m = SlippageModel()
        assert m.slippage(100.0, 1, Market.KOSPI, Side.BUY, at_open_or_close=False) == 0.0
        assert m.slippage(100.0, 1, Market.KOSPI, Side.BUY, at_open_or_close=True) == 0.0


# ---------------------------------------------------------------------------
# SlippageModel — enabled, KOSPI
# ---------------------------------------------------------------------------

class TestSlippageModelKospiEnabled:
    """
    KOSPI spread_bps = 8.0 (DEFAULT), open_close_extra_bps = 5.0 (default)

    at_open_or_close=True  → total_bps = 8 + 5 = 13
    at_open_or_close=False → total_bps = 8 + 0 = 8

    price=70_000, qty=10 → notional = 700_000

    at open : 700_000 * 13 / 10_000 = 9_100.0
    not open: 700_000 *  8 / 10_000 = 5_600.0
    """

    def setup_method(self):
        self.m = SlippageModel(enabled=True)
        self.price = 70_000.0
        self.qty = 10
        self.notional = self.price * self.qty  # 700_000

    def test_at_open_buy(self):
        expected = self.notional * (8.0 + 5.0) / 10_000
        got = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.BUY,
                              at_open_or_close=True)
        assert abs(got - expected) < 1e-9

    def test_at_open_sell(self):
        # Cost is positive for both sides — sell is also adverse
        expected = self.notional * (8.0 + 5.0) / 10_000
        got = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.SELL,
                              at_open_or_close=True)
        assert abs(got - expected) < 1e-9

    def test_not_at_open(self):
        expected = self.notional * 8.0 / 10_000
        got = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.BUY,
                              at_open_or_close=False)
        assert abs(got - expected) < 1e-9

    def test_side_independent(self):
        buy_cost  = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.BUY)
        sell_cost = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.SELL)
        assert buy_cost == sell_cost

    def test_at_open_default_is_true(self):
        # Default at_open_or_close=True
        with_open  = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.BUY,
                                     at_open_or_close=True)
        default    = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.BUY)
        assert with_open == default

    def test_at_open_adds_extra_vs_not_at_open(self):
        at_open = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.BUY,
                                  at_open_or_close=True)
        not_open = self.m.slippage(self.price, self.qty, Market.KOSPI, Side.BUY,
                                   at_open_or_close=False)
        delta = at_open - not_open
        expected_delta = self.notional * 5.0 / 10_000
        assert abs(delta - expected_delta) < 1e-9

    def test_hand_verified_at_open_value(self):
        # 70_000 * 10 * (8+5) / 10_000 = 700_000 * 13 / 10_000 = 910.0
        assert abs(self.m.slippage(70_000.0, 10, Market.KOSPI, Side.BUY,
                                   at_open_or_close=True) - 910.0) < 1e-6

    def test_hand_verified_not_at_open_value(self):
        # 70_000 * 10 * 8 / 10_000 = 700_000 * 8 / 10_000 = 560.0
        assert abs(self.m.slippage(70_000.0, 10, Market.KOSPI, Side.BUY,
                                   at_open_or_close=False) - 560.0) < 1e-6


# ---------------------------------------------------------------------------
# SlippageModel — enabled, NASDAQ
# ---------------------------------------------------------------------------

class TestSlippageModelNasdaqEnabled:
    """
    NASDAQ spread_bps = 3.0 (DEFAULT), open_close_extra_bps = 5.0

    price=200.0, qty=50 → notional = 10_000

    at open : 10_000 * (3 + 5) / 10_000 = 8.0
    not open: 10_000 * 3 / 10_000       = 3.0
    """

    def setup_method(self):
        self.m = SlippageModel(enabled=True)
        self.price = 200.0
        self.qty = 50
        self.notional = self.price * self.qty  # 10_000

    def test_at_open_buy(self):
        expected = self.notional * (3.0 + 5.0) / 10_000
        got = self.m.slippage(self.price, self.qty, Market.NASDAQ, Side.BUY,
                              at_open_or_close=True)
        assert abs(got - expected) < 1e-9

    def test_at_open_sell(self):
        expected = self.notional * (3.0 + 5.0) / 10_000
        got = self.m.slippage(self.price, self.qty, Market.NASDAQ, Side.SELL,
                              at_open_or_close=True)
        assert abs(got - expected) < 1e-9

    def test_not_at_open(self):
        expected = self.notional * 3.0 / 10_000
        got = self.m.slippage(self.price, self.qty, Market.NASDAQ, Side.BUY,
                              at_open_or_close=False)
        assert abs(got - expected) < 1e-9

    def test_side_independent(self):
        buy  = self.m.slippage(self.price, self.qty, Market.NASDAQ, Side.BUY)
        sell = self.m.slippage(self.price, self.qty, Market.NASDAQ, Side.SELL)
        assert buy == sell

    def test_hand_verified_at_open(self):
        # 200 * 50 * 8 / 10_000 = 8.0
        assert abs(self.m.slippage(200.0, 50, Market.NASDAQ, Side.BUY,
                                   at_open_or_close=True) - 8.0) < 1e-9

    def test_hand_verified_not_at_open(self):
        # 200 * 50 * 3 / 10_000 = 3.0
        assert abs(self.m.slippage(200.0, 50, Market.NASDAQ, Side.BUY,
                                   at_open_or_close=False) - 3.0) < 1e-9


# ---------------------------------------------------------------------------
# SlippageModel — custom spread_bps_by_market
# ---------------------------------------------------------------------------

class TestSlippageModelCustom:
    def test_custom_spread_overrides_default(self):
        m = SlippageModel(spread_bps_by_market={Market.KOSPI: 20.0}, enabled=True,
                          open_close_extra_bps=0.0)
        # notional = 100 * 1 = 100; cost = 100 * 20 / 10_000 = 0.2
        assert abs(m.slippage(100.0, 1, Market.KOSPI, Side.BUY) - 0.2) < 1e-9

    def test_market_not_in_map_returns_zero(self):
        # SlippageModel with empty market map and no open/close extra → 0.0 spread cost
        # open_close_extra_bps=0 so the total_bps = 0 + 0 = 0 → zero cost
        m = SlippageModel(spread_bps_by_market={}, open_close_extra_bps=0.0, enabled=True)
        assert m.slippage(100.0, 10, Market.NASDAQ, Side.BUY) == 0.0

    def test_market_not_in_map_only_extra_bps_applies(self):
        # When market not in map, spread_bps=0 but open_close_extra still applies
        # 100 * 10 * 5 / 10_000 = 0.5
        m = SlippageModel(spread_bps_by_market={}, open_close_extra_bps=5.0, enabled=True)
        assert abs(m.slippage(100.0, 10, Market.NASDAQ, Side.BUY,
                              at_open_or_close=True) - 0.5) < 1e-9
        # at_open_or_close=False → 0.0 (no spread, no extra)
        assert m.slippage(100.0, 10, Market.NASDAQ, Side.BUY,
                          at_open_or_close=False) == 0.0

    def test_custom_open_close_extra(self):
        m = SlippageModel(spread_bps_by_market={Market.NASDAQ: 2.0},
                          open_close_extra_bps=10.0, enabled=True)
        # notional = 50 * 100 = 5_000; at open: (2+10)/10_000 * 5_000 = 6.0
        got = m.slippage(50.0, 100, Market.NASDAQ, Side.BUY, at_open_or_close=True)
        assert abs(got - 6.0) < 1e-9


# ---------------------------------------------------------------------------
# SimulatedExecutionHandler — parity micro-check (slippage=None)
# ---------------------------------------------------------------------------

class TestSimulatedExecNoSlippage:
    """slippage=None → identical commission as without slippage kwarg.

    Fill timing: order submitted via submit_order(), then fills on the NEXT
    on_bar() call for that symbol (day=1 bar fills the order submitted before it).
    """

    def test_none_slippage_identical_to_old_default(self):
        """Handler with slippage=None produces same commission as one without slippage arg."""
        # Submit order, then call on_bar once → fills at bar1.open
        order_id = uuid4()
        bar1 = _bar(NASDAQ_SYM, open_=100.0, day=1)

        # Old-style: no slippage arg
        ex_old = SimulatedExecutionHandler(BpsCostModel(5.0))
        ex_old.submit_order(OrderEvent(order_id, NASDAQ_SYM, T0, Side.BUY, 10))
        fills_old = ex_old.on_bar(bar1)

        # New-style: slippage=None explicitly
        ex_new = SimulatedExecutionHandler(BpsCostModel(5.0), slippage=None)
        ex_new.submit_order(OrderEvent(order_id, NASDAQ_SYM, T0, Side.BUY, 10))
        fills_new = ex_new.on_bar(bar1)

        assert len(fills_old) == 1
        assert len(fills_new) == 1
        assert fills_old[0].commission == fills_new[0].commission
        assert fills_old[0].price == fills_new[0].price

    def test_zero_bps_none_slippage_zero_commission(self):
        ex = SimulatedExecutionHandler(BpsCostModel(0.0), slippage=None)
        ex.submit_order(_order(NASDAQ_SYM, Side.BUY, qty=10))
        fills = ex.on_bar(_bar(NASDAQ_SYM, open_=100.0, day=1))
        assert len(fills) == 1
        assert fills[0].commission == 0.0


# ---------------------------------------------------------------------------
# SimulatedExecutionHandler — with slippage enabled
# ---------------------------------------------------------------------------

class TestSimulatedExecWithSlippage:
    """
    BpsCostModel(0.0) + SlippageModel(enabled=True, KOSPI 8bps, extra 5bps)

    price=70_000, qty=5 → notional = 70_000 * 5 = 350_000
    commission = 0  (BpsCostModel 0.0)
    slippage at open = 350_000 * (8 + 5) / 10_000 = 350_000 * 13 / 10_000 = 455.0
    total commission in FillEvent = 0 + 455 = 455.0

    Fill timing: submit_order() then on_bar() → fills immediately on that bar.
    """

    PRICE = 70_000.0
    QTY = 5
    NOTIONAL = PRICE * QTY          # 350_000
    SLIP_BPS = 8.0 + 5.0            # spread + open_close_extra = 13
    EXPECTED_SLIP = NOTIONAL * SLIP_BPS / 10_000  # 350_000 * 13 / 10_000 = 455.0

    def _make_handler(self) -> SimulatedExecutionHandler:
        slip = SlippageModel(enabled=True)
        return SimulatedExecutionHandler(BpsCostModel(0.0), slippage=slip)

    def test_fill_commission_includes_slippage(self):
        ex = self._make_handler()
        ex.submit_order(_order(KOSPI_SYM, Side.BUY, qty=self.QTY))
        fills = ex.on_bar(_bar(KOSPI_SYM, open_=self.PRICE, day=1))
        assert len(fills) == 1
        assert abs(fills[0].commission - self.EXPECTED_SLIP) < 1e-6

    def test_fill_price_is_still_bar_open(self):
        """Fill price stays bar.open — slippage is modelled in commission, not price."""
        ex = self._make_handler()
        ex.submit_order(_order(KOSPI_SYM, Side.BUY, qty=self.QTY))
        fills = ex.on_bar(_bar(KOSPI_SYM, open_=self.PRICE, day=1))
        assert len(fills) == 1
        assert fills[0].price == self.PRICE

    def test_sell_commission_same_as_buy(self):
        """Slippage is side-independent — cost positive for both buy and sell."""
        ex_buy  = self._make_handler()
        ex_sell = self._make_handler()

        ex_buy.submit_order(_order(KOSPI_SYM, Side.BUY,  qty=self.QTY))
        ex_sell.submit_order(_order(KOSPI_SYM, Side.SELL, qty=self.QTY))

        fills_buy  = ex_buy.on_bar(_bar(KOSPI_SYM, open_=self.PRICE, day=1))
        fills_sell = ex_sell.on_bar(_bar(KOSPI_SYM, open_=self.PRICE, day=1))

        assert len(fills_buy) == 1 and len(fills_sell) == 1
        assert fills_buy[0].commission == fills_sell[0].commission

    def test_slippage_adds_to_nonzero_commission(self):
        """When BpsCostModel is nonzero, slippage is added on top.

        BpsCostModel(10.0) → commission = 70_000 * 5 * 10/10_000 = 3_500
        Slippage at open   = 350_000 * 13/10_000                 =   455
        Total              =                                        3_955
        """
        slip = SlippageModel(enabled=True)
        ex = SimulatedExecutionHandler(BpsCostModel(10.0), slippage=slip)
        ex.submit_order(_order(KOSPI_SYM, Side.BUY, qty=self.QTY))
        fills = ex.on_bar(_bar(KOSPI_SYM, open_=self.PRICE, day=1))
        assert len(fills) == 1
        base_commission = self.PRICE * self.QTY * 10.0 / 10_000  # 3_500
        expected = base_commission + self.EXPECTED_SLIP           # 3_955
        assert abs(fills[0].commission - expected) < 1e-6

    def test_nasdaq_slippage_hand_verified(self):
        """
        NASDAQ: price=200, qty=50 → notional = 200 * 50 = 10_000
        slippage at open = 10_000 * (3+5) / 10_000 = 8.0
        """
        slip = SlippageModel(enabled=True)
        ex = SimulatedExecutionHandler(BpsCostModel(0.0), slippage=slip)
        ex.submit_order(_order(NASDAQ_SYM, Side.BUY, qty=50))
        fills = ex.on_bar(_bar(NASDAQ_SYM, open_=200.0, day=1))
        assert len(fills) == 1
        assert abs(fills[0].commission - 8.0) < 1e-9


# ---------------------------------------------------------------------------
# tradable() — liquidity/sanity filter
# ---------------------------------------------------------------------------

class TestTradable:
    def _bar_with(self, close: float, volume: int) -> BarEvent:
        ts = T0 + timedelta(days=1)
        return BarEvent(KOSPI_SYM, ts, open=close, high=close+1, low=close-1,
                        close=close, volume=volume)

    def test_default_thresholds_pass_normal_bar(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=70_000.0, volume=100_000)
        assert tradable(b) is True

    def test_rejects_zero_price(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=0.0, volume=100_000)
        assert tradable(b) is False

    def test_rejects_below_min_price(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=0.5, volume=100_000)
        assert tradable(b) is False

    def test_exactly_min_price_passes(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=1.0, volume=100_000)
        assert tradable(b) is True

    def test_rejects_zero_volume_when_min_volume_1(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=100.0, volume=0)
        assert tradable(b, min_volume=1) is False

    def test_zero_volume_passes_default_min_volume_zero(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=100.0, volume=0)
        assert tradable(b) is True  # default min_volume=0

    def test_rejects_below_min_volume(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=100.0, volume=999)
        assert tradable(b, min_volume=1000) is False

    def test_exactly_min_volume_passes(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=100.0, volume=1000)
        assert tradable(b, min_volume=1000) is True

    def test_custom_min_price(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=4.99, volume=100)
        assert tradable(b, min_price=5.0) is False
        assert tradable(b, min_price=4.99) is True

    def test_both_fail(self):
        from trader.execution.costs import tradable
        b = self._bar_with(close=0.5, volume=0)
        assert tradable(b, min_price=1.0, min_volume=1) is False


# ---------------------------------------------------------------------------
# DEFAULT_SLIPPAGE_BPS sanity checks
# ---------------------------------------------------------------------------

def test_default_slippage_bps_has_kospi_and_nasdaq():
    assert Market.KOSPI in DEFAULT_SLIPPAGE_BPS
    assert Market.NASDAQ in DEFAULT_SLIPPAGE_BPS

def test_default_slippage_kospi_is_conservative():
    # Should be >= 5 bps (conservative floor for KR retail)
    assert DEFAULT_SLIPPAGE_BPS[Market.KOSPI] >= 5.0

def test_default_slippage_nasdaq_is_positive():
    assert DEFAULT_SLIPPAGE_BPS[Market.NASDAQ] > 0.0
