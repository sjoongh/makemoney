# trader/live/pretrade.py
"""Pre-trade risk gate + max-orders circuit breaker.

Deterministic, pure-logic — no I/O, no network calls.
Applied at submission time (separate from RiskManager sizing).
"""
from __future__ import annotations

from dataclasses import dataclass

from trader.core.events import OrderEvent, Side


@dataclass(frozen=True)
class PreTradeLimits:
    max_order_notional_krw: float = 5_000_000   # per-order KRW cap
    max_position_weight: float = 0.30           # per-symbol weight cap (post-trade)
    max_orders_per_run: int = 10                # circuit-breaker count
    fat_finger_qty: int = 10_000               # absolute qty sanity ceiling
    price_sanity_pct: float = 0.30             # reject if decision price deviates >30% from last_close
    cash_buffer_pct: float = 0.01              # keep 1% cash buffer for fees/tax


@dataclass(frozen=True)
class GateResult:
    approved: bool
    reason: str = ""   # reason_code when blocked; empty string when approved


class PreTradeRiskGate:
    """Submission-time risk gate.

    Parameters
    ----------
    limits:
        Immutable limits config.
    fx:
        FxRates — used for KRW notional conversion (``fx.to_krw(amount, ccy)``).
    """

    def __init__(self, limits: PreTradeLimits, fx) -> None:
        self.limits = limits
        self.fx = fx

    def check_order(
        self,
        order: OrderEvent,
        *,
        decision_price: float,
        last_close: float,
        portfolio,
    ) -> GateResult:
        """Evaluate all pre-trade checks and return an approval/block result.

        Checks are applied in this order (first failure short-circuits):
          1. FAT_FINGER_QTY  — quantity <= 0 or > fat_finger_qty
          2. PRICE_SANITY    — last_close <= 0 or |decision/last_close - 1| > price_sanity_pct
          3. MAX_ORDER_NOTIONAL — notional_krw > max_order_notional_krw
          4. INSUFFICIENT_CASH (BUY only)
          5. MAX_POSITION_WEIGHT (BUY only)

        SELL orders skip checks 4 and 5 (risk-reducing).
        """
        lim = self.limits
        ccy = order.symbol.currency

        # 1. Fat-finger quantity check (applies to all sides)
        if order.quantity <= 0 or order.quantity > lim.fat_finger_qty:
            return GateResult(False, "FAT_FINGER_QTY")

        # 2. Price sanity (applies to all sides)
        if last_close <= 0 or abs(decision_price / last_close - 1.0) > lim.price_sanity_pct:
            return GateResult(False, "PRICE_SANITY")

        # 3. Notional cap (applies to all sides)
        notional_krw = self.fx.to_krw(decision_price * order.quantity, ccy)
        if notional_krw > lim.max_order_notional_krw:
            return GateResult(False, "MAX_ORDER_NOTIONAL")

        # BUY-only checks
        if order.side == Side.BUY:
            # 4. Cash buffer check
            cash_krw = portfolio.cash.get("KRW", 0.0)
            if notional_krw * (1.0 + lim.cash_buffer_pct) > cash_krw:
                return GateResult(False, "INSUFFICIENT_CASH")

            # 5. Post-trade position weight check
            equity = portfolio.equity_krw()
            if equity > 0:
                current_weight = portfolio.position_weight(order.symbol)
                post_trade_weight = current_weight + notional_krw / equity
                if post_trade_weight > lim.max_position_weight:
                    return GateResult(False, "MAX_POSITION_WEIGHT")

        return GateResult(True)


class RunCircuitBreaker:
    """Counts approved order submissions in a single run.

    Once ``max_orders_per_run`` approved orders have been recorded,
    ``allow()`` returns False for all subsequent calls.
    """

    def __init__(self, max_orders_per_run: int) -> None:
        self._max = max_orders_per_run
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    def allow(self) -> bool:
        """Return True and increment counter if under the cap; else False."""
        if self._count >= self._max:
            return False
        self._count += 1
        return True
