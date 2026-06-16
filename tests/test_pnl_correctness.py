# tests/test_pnl_correctness.py
"""
INDEPENDENT hand-calculated PnL / accounting correctness fixtures.
P0 foundation: every expected value is derived from arithmetic written in
comments, NOT from the engine itself — circular derivation is explicitly
avoided.  These tests validate that the engine's cash/position/equity_krw
accounting is CORRECT, not merely internally consistent.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from trader.core.events import BarEvent, FillEvent, Market, OrderEvent, Side, Symbol
from trader.execution.costs import MarketCostModel, MarketCostConfig
from trader.execution.simulated import SimulatedExecutionHandler
from trader.strategy.portfolio import FxRates, Portfolio

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_KRW_ONLY_FX = FxRates({"KRW": 1.0})
_FX_1300 = FxRates({"USD": 1300.0, "KRW": 1.0})

KOSPI_SYM = Symbol("005930", Market.KOSPI, "KRW")
AAPL = Symbol("AAPL", Market.NASDAQ, "USD")
TSLA = Symbol("TSLA", Market.NASDAQ, "USD")


def _ts(offset_days: int = 0) -> datetime:
    return datetime(2026, 1, 3, tzinfo=timezone.utc) + timedelta(days=offset_days)


def _bar(sym: Symbol, open_: float, close: float, day: int = 0) -> BarEvent:
    return BarEvent(sym, _ts(day), open_, close, open_, close, 1_000)


def _fill(sym: Symbol, side: Side, qty: int, price: float,
          commission: float, ccy: str) -> FillEvent:
    return FillEvent(uuid4(), sym, _ts(), side, qty, price, commission, ccy)


# ---------------------------------------------------------------------------
# Scenario 1 — Single KRW round-trip (KOSPI, flat round trip)
# ---------------------------------------------------------------------------

def test_sc1_krw_round_trip():
    """
    Hand-calc:
        initial cash = 2_000_000 KRW

        BUY 100 @ 10_000 KRW (KOSPI)
          notional      = 100 * 10_000        = 1_000_000 KRW
          buy_cost      = 1_000_000 * 1.40527/10_000 = 140.527 KRW
          cash_after_buy = 2_000_000 - 1_000_000 - 140.527 = 999_859.473 KRW
          position      = 100

        SELL 100 @ 11_000 KRW (KOSPI)
          notional      = 100 * 11_000        = 1_100_000 KRW
          sell_bps      = 1.40527 + 20.0      = 21.40527
          sell_cost     = 1_100_000 * 21.40527/10_000 = 2_354.5797 KRW
          cash_final    = 999_859.473 + 1_100_000 - 2_354.5797 = 2_097_504.8933 KRW
          position      = 0

        realized_pnl = 100*(11_000-10_000) - 140.527 - 2_354.5797
                     = 100_000 - 2_495.1067
                     = 97_504.8933 KRW

        equity_krw (no open position) == cash_final == 2_097_504.8933
    """
    cost = MarketCostModel()
    pf = Portfolio({"KRW": 2_000_000.0}, _KRW_ONLY_FX)

    # --- BUY ---
    buy_notional = 100 * 10_000                           # 1_000_000
    buy_cost = buy_notional * 1.40527 / 10_000            # 140.527
    pf.apply_fill(_fill(KOSPI_SYM, Side.BUY, 100, 10_000.0, buy_cost, "KRW"))

    assert pf.position(KOSPI_SYM) == 100
    assert abs(pf.cash["KRW"] - 999_859.473) < 0.001, (
        f"cash after buy expected 999_859.473, got {pf.cash['KRW']}"
    )

    # --- SELL ---
    sell_notional = 100 * 11_000                          # 1_100_000
    sell_bps = 1.40527 + 20.0                             # 21.40527
    sell_cost = sell_notional * sell_bps / 10_000         # 2_354.5797
    pf.apply_fill(_fill(KOSPI_SYM, Side.SELL, 100, 11_000.0, sell_cost, "KRW"))

    # Expected final values
    expected_cash = 2_097_504.8933
    expected_realized_pnl = 97_504.8933

    assert pf.position(KOSPI_SYM) == 0
    assert abs(pf.cash["KRW"] - expected_cash) < 0.001, (
        f"cash_final expected {expected_cash}, got {pf.cash['KRW']}"
    )
    # With no open position, equity == cash
    assert abs(pf.equity_krw() - expected_cash) < 0.001, (
        f"equity_krw expected {expected_cash}, got {pf.equity_krw()}"
    )
    # Verify realized PnL (initial_cash + pnl == final_cash)
    assert abs((pf.cash["KRW"] - 2_000_000.0) - expected_realized_pnl) < 0.001


# ---------------------------------------------------------------------------
# Scenario 2 — USD buy, KRW-settled (FX conversion)
# ---------------------------------------------------------------------------

def test_sc2_usd_buy_krw_settled():
    """
    Hand-calc  (fx USD=1300):
        initial cash = 13_000_000 KRW

        BUY 10 AAPL @ $100 (NASDAQ)
          buy_cost_usd  = 10*100 * 35.0/10_000    # comm 25bps + fx 10bps = 35bps
                        = 1_000 * 0.0035 = 3.5 USD
          notional_krw  = 10*100*1_300             = 1_300_000 KRW
          comm_krw      = 3.5 * 1_300              = 4_550 KRW
          cash_after    = 13_000_000 - 1_300_000 - 4_550 = 11_695_450 KRW
          position      = 10 AAPL

        Mark at $120:
          pos_value_krw = 10 * 120 * 1_300         = 1_560_000 KRW
          equity_krw    = 11_695_450 + 1_560_000   = 13_255_450 KRW
    """
    cost = MarketCostModel()
    pf = Portfolio({"KRW": 13_000_000.0}, _FX_1300)

    buy_cost_usd = 10 * 100.0 * 35.0 / 10_000   # 3.5 USD  (35 bps: 25 comm + 10 fx)
    pf.apply_fill(_fill(AAPL, Side.BUY, 10, 100.0, buy_cost_usd, "USD"))

    assert pf.position(AAPL) == 10
    assert abs(pf.cash["KRW"] - 11_695_450.0) < 0.001, (
        f"cash after USD buy expected 11_695_450, got {pf.cash['KRW']}"
    )

    # Mark at $120
    pf.mark(_bar(AAPL, 120.0, 120.0))
    expected_equity = 13_255_450.0   # 11_695_450 + 10*120*1300
    assert abs(pf.equity_krw() - expected_equity) < 0.001, (
        f"equity_krw at $120 mark expected {expected_equity}, got {pf.equity_krw()}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Multiple partial fills accumulate correctly
# ---------------------------------------------------------------------------

def test_sc3_multiple_partial_fills():
    """
    Hand-calc:
        initial cash = 5_000_000 KRW
        KOSPI stock @ 1_000 KRW, comm_bps = 1.40527

        Fill-1  BUY 50 @ 1_000
          cost  = 50*1_000 * 1.40527/10_000 = 50_000 * 0.000140527 = 7.02635 KRW
          cash  = 5_000_000 - 50_000 - 7.02635 = 4_949_992.97365
          pos   = 50

        Fill-2  BUY 30 @ 1_000
          cost  = 30*1_000 * 1.40527/10_000 = 30_000 * 0.000140527 = 4.21581 KRW
          cash  = 4_949_992.97365 - 30_000 - 4.21581 = 4_919_988.75784
          pos   = 80

        Fill-3  BUY 20 @ 1_000
          cost  = 20*1_000 * 1.40527/10_000 = 20_000 * 0.000140527 = 2.81054 KRW
          cash  = 4_919_988.75784 - 20_000 - 2.81054 = 4_899_985.9473
          pos   = 100

        total notional paid = 100*1_000 = 100_000
        total cost          = 7.02635+4.21581+2.81054 = 14.0527 KRW
        total cash spent    = 100_014.0527 KRW
    """
    comm_bps = 1.40527
    pf = Portfolio({"KRW": 5_000_000.0}, _KRW_ONLY_FX)

    def kospi_buy_cost(qty: int, price: float) -> float:
        return qty * price * comm_bps / 10_000

    # Fill 1
    c1 = kospi_buy_cost(50, 1_000)   # 7.02635
    pf.apply_fill(_fill(KOSPI_SYM, Side.BUY, 50, 1_000.0, c1, "KRW"))
    assert pf.position(KOSPI_SYM) == 50
    assert abs(pf.cash["KRW"] - 4_949_992.97365) < 0.001

    # Fill 2
    c2 = kospi_buy_cost(30, 1_000)   # 4.21581
    pf.apply_fill(_fill(KOSPI_SYM, Side.BUY, 30, 1_000.0, c2, "KRW"))
    assert pf.position(KOSPI_SYM) == 80
    assert abs(pf.cash["KRW"] - 4_919_988.75784) < 0.001

    # Fill 3
    c3 = kospi_buy_cost(20, 1_000)   # 2.81054
    pf.apply_fill(_fill(KOSPI_SYM, Side.BUY, 20, 1_000.0, c3, "KRW"))
    assert pf.position(KOSPI_SYM) == 100
    assert abs(pf.cash["KRW"] - 4_899_985.9473) < 0.001

    # Total cost check
    total_cost = c1 + c2 + c3        # 14.0527
    assert abs(total_cost - 14.0527) < 0.001
    expected_cash = 5_000_000.0 - 100_000.0 - total_cost
    assert abs(pf.cash["KRW"] - expected_cash) < 0.001


# ---------------------------------------------------------------------------
# Scenario 4 — Next-open gap execution
# ---------------------------------------------------------------------------

def test_sc4_next_open_fill_price():
    """
    SimulatedExecutionHandler: order submitted after bar-t close fills at bar-t+1
    OPEN — NOT at t's close, NOT at t+1's close.

    Hand-calc:
        Bar t+1: open=105, close=115
        Order submitted (side=BUY, qty=10) before bar t+1 arrives.
        Expected fill price = 105  (bar open)

        With zero cost (BpsCostModel 0.0):
          notional_krw = 10 * 105 * 1 = 1_050  KRW deducted
          cash = 1_000_000 - 1_050 = 998_950
    """
    from trader.execution.costs import BpsCostModel

    handler = SimulatedExecutionHandler(cost_model=BpsCostModel(0.0))
    pf = Portfolio({"KRW": 1_000_000.0}, _KRW_ONLY_FX)

    order = OrderEvent(uuid4(), KOSPI_SYM, _ts(0), Side.BUY, 10)
    handler.submit_order(order)

    # Simulate bar arriving the next day: open=105, close=115
    bar_next = BarEvent(KOSPI_SYM, _ts(1), 105.0, 120.0, 100.0, 115.0, 500)
    fills = handler.on_bar(bar_next)

    assert len(fills) == 1, "exactly one fill expected"
    fill = fills[0]

    # Fill must be at OPEN (105), not close (115)
    assert fill.price == 105.0, (
        f"fill price must be bar open 105.0, got {fill.price} "
        f"(if 115.0 → lookahead bug: using close instead of open)"
    )
    assert fill.quantity == 10
    assert fill.side == Side.BUY

    pf.apply_fill(fill)
    # notional_krw = 10 * 105 = 1_050; comm = 0; cash = 1_000_000 - 1_050 = 998_950
    assert abs(pf.cash["KRW"] - 998_950.0) < 0.001, (
        f"cash expected 998_950, got {pf.cash['KRW']}"
    )
    assert pf.position(KOSPI_SYM) == 10


# ---------------------------------------------------------------------------
# Scenario 5 — No fill on missing/absent symbol bar
# ---------------------------------------------------------------------------

def test_sc5_no_fill_when_symbol_bar_absent():
    """
    A pending order for TSLA (NASDAQ/USD).  Only bars for AAPL arrive.
    Expected: zero fills, cash and position unchanged.

    Hand-calc: trivial — nothing changes.
    """
    from trader.execution.costs import BpsCostModel

    handler = SimulatedExecutionHandler(cost_model=BpsCostModel(0.0))
    pf = Portfolio({"KRW": 5_000_000.0}, _FX_1300)

    order = OrderEvent(uuid4(), TSLA, _ts(0), Side.BUY, 5)
    handler.submit_order(order)

    # Several bars for AAPL (different symbol) — should not fill TSLA order
    for day in range(3):
        bar_aapl = _bar(AAPL, 150.0 + day, 152.0 + day, day)
        fills = handler.on_bar(bar_aapl)
        assert fills == [], f"day {day}: unexpected fill for different symbol"

    # Portfolio untouched
    assert pf.cash["KRW"] == 5_000_000.0
    assert pf.position(TSLA) == 0

    # Order still pending
    assert len(handler._pending) == 1
    assert handler._pending[0].symbol == TSLA


# ---------------------------------------------------------------------------
# Scenario 6 — Cost correctness: exact KRW amounts
# ---------------------------------------------------------------------------

def test_sc6_kospi_sell_tax_exact():
    """
    Hand-calc:
        KOSPI sell, qty=200, price=5_000 KRW
          notional = 200 * 5_000             = 1_000_000 KRW
          commission = 1_000_000 * 1.40527/10_000 = 140.527 KRW
          sell_tax   = 1_000_000 * 20.0/10_000    = 2_000.0 KRW
          total cost = 1_000_000 * 21.40527/10_000 = 2_140.527 KRW

    The 20 bps sell_tax_bps is the 2026 증권거래세 rate (STT 0.05% + 농특세 0.15%).
    """
    cost = MarketCostModel()
    computed = cost.commission(price=5_000.0, quantity=200,
                               market=Market.KOSPI, side=Side.SELL)
    expected = 2_140.527   # hand-computed above
    assert abs(computed - expected) < 0.001, (
        f"KOSPI sell cost expected {expected}, got {computed}"
    )

    # Decompose: tax alone = 2_000.0 KRW = 1_000_000 * 20bps
    # commission alone = 140.527 KRW
    assert abs(computed - 140.527 - 2_000.0) < 0.001   # tax + comm = total

    # Apply to portfolio: start with 3_000_000, buy at 5_000 (cost=140.527), then sell
    pf = Portfolio({"KRW": 3_000_000.0}, _KRW_ONLY_FX)
    buy_cost = 200 * 5_000 * 1.40527 / 10_000   # 140.527
    pf.apply_fill(_fill(KOSPI_SYM, Side.BUY, 200, 5_000.0, buy_cost, "KRW"))
    # cash = 3_000_000 - 1_000_000 - 140.527 = 1_999_859.473
    pf.apply_fill(_fill(KOSPI_SYM, Side.SELL, 200, 5_000.0, computed, "KRW"))
    # cash = 1_999_859.473 + 1_000_000 - 2_140.527 = 2_997_718.946
    expected_cash = 3_000_000.0 - buy_cost - computed   # round trip at same price
    assert abs(pf.cash["KRW"] - expected_cash) < 0.001, (
        f"cash after round-trip expected {expected_cash}, got {pf.cash['KRW']}"
    )


def test_sc6_nasdaq_buy_cost_35bps():
    """
    Hand-calc:
        NASDAQ buy, qty=50, price=$200
          notional   = 50 * 200              = 10_000 USD
          commission = 10_000 * 25.0/10_000  = 25.0 USD
          fx_spread  = 10_000 * 10.0/10_000  = 10.0 USD
          total cost = 10_000 * 35.0/10_000  = 35.0 USD
          (no SEC fee, no FINRA TAF on buys)
    """
    cost = MarketCostModel()
    computed = cost.commission(price=200.0, quantity=50,
                               market=Market.NASDAQ, side=Side.BUY)
    expected = 35.0   # hand-computed above
    assert abs(computed - expected) < 1e-9, (
        f"NASDAQ buy cost expected {expected} USD, got {computed}"
    )


def test_sc6_nasdaq_sell_cost_with_sec_and_taf():
    """
    Hand-calc:
        NASDAQ sell, qty=100, price=$100
          notional        = 100 * 100              = 10_000 USD
          commission      = 10_000 * 25.0/10_000   = 25.0 USD
          sec_fee (sell)  = 10_000 * 0.206/10_000  = 0.206 USD
          fx_spread       = 10_000 * 10.0/10_000   = 10.0 USD
          FINRA TAF       = min(0.000195*100, 9.79) = min(0.0195, 9.79) = 0.0195 USD
          total cost      = 25.0 + 0.206 + 10.0 + 0.0195 = 35.2255 USD
    """
    cost = MarketCostModel()
    computed = cost.commission(price=100.0, quantity=100,
                               market=Market.NASDAQ, side=Side.SELL)
    expected = 35.2255
    assert abs(computed - expected) < 0.0001, (
        f"NASDAQ sell cost expected {expected} USD, got {computed}"
    )


# ---------------------------------------------------------------------------
# Scenario 7 — equity_krw identity: cash_KRW + sum(pos*mark*fx) == equity_krw
# ---------------------------------------------------------------------------

def test_sc7_equity_krw_identity():
    """
    After a sequence of fills+marks, verify the identity:
        equity_krw == KRW_cash + sum(pos_qty * mark_price * fx_rate)

    Hand-calc:
        initial cash = 5_000_000 KRW
        fx USD=1300

        BUY 10 AAPL @ $100 (NASDAQ, comm 35bps → 3.5 USD)
          notional_krw = 10*100*1300 = 1_300_000
          comm_krw     = 3.5*1300   = 4_550
          cash_krw     = 5_000_000 - 1_300_000 - 4_550 = 3_695_450

        Mark AAPL at $110:
          pos_value_krw = 10 * 110 * 1300 = 1_430_000

        BUY 50 KOSPI @ 20_000 KRW (comm 1.40527bps)
          notional_krw = 50*20_000 = 1_000_000
          comm_krw     = 1_000_000 * 1.40527/10_000 = 140.527
          cash_krw     = 3_695_450 - 1_000_000 - 140.527 = 2_695_309.473

        Mark KOSPI at 21_000:
          pos_value_krw = 50 * 21_000 * 1 = 1_050_000

        Identity:
          equity_krw = cash_krw + pos_value_aapl_krw + pos_value_kospi_krw
                     = 2_695_309.473 + 1_430_000 + 1_050_000
                     = 5_175_309.473
    """
    pf = Portfolio({"KRW": 5_000_000.0}, _FX_1300)

    # BUY AAPL
    aapl_buy_cost_usd = 10 * 100.0 * 35.0 / 10_000   # 3.5 USD
    pf.apply_fill(_fill(AAPL, Side.BUY, 10, 100.0, aapl_buy_cost_usd, "USD"))
    # cash = 5_000_000 - 10*100*1300 - 3.5*1300 = 5_000_000 - 1_300_000 - 4_550 = 3_695_450
    assert abs(pf.cash["KRW"] - 3_695_450.0) < 0.001

    # BUY KOSPI
    kospi_buy_cost = 50 * 20_000 * 1.40527 / 10_000   # 140.527 KRW
    pf.apply_fill(_fill(KOSPI_SYM, Side.BUY, 50, 20_000.0, kospi_buy_cost, "KRW"))
    # cash = 3_695_450 - 1_000_000 - 140.527 = 2_695_309.473
    assert abs(pf.cash["KRW"] - 2_695_309.473) < 0.001

    # Mark both positions
    pf.mark(_bar(AAPL, 110.0, 110.0))        # mark AAPL @ $110
    pf.mark(_bar(KOSPI_SYM, 21_000.0, 21_000.0))  # mark KOSPI @ 21_000 KRW

    # Hand-computed sub-totals
    cash_krw = 2_695_309.473
    pos_aapl_krw = 10 * 110.0 * 1300.0    # 1_430_000
    pos_kospi_krw = 50 * 21_000.0 * 1.0   # 1_050_000
    expected_equity = cash_krw + pos_aapl_krw + pos_kospi_krw  # 5_175_309.473

    # Identity assertion: engine must produce exactly the hand-computed value
    engine_equity = pf.equity_krw()
    assert abs(engine_equity - expected_equity) < 0.001, (
        f"equity_krw identity failed: "
        f"expected {expected_equity} (cash {cash_krw} + aapl_pos {pos_aapl_krw} "
        f"+ kospi_pos {pos_kospi_krw}), got {engine_equity}"
    )

    # Also verify position_value_krw helpers are consistent with the identity
    assert abs(pf.position_value_krw(AAPL) - pos_aapl_krw) < 0.001
    assert abs(pf.position_value_krw(KOSPI_SYM) - pos_kospi_krw) < 0.001
