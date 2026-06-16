# trader/live/daily.py
"""Daily once-per-bar runner: warm up indicators on history, act only on the latest bar."""
from __future__ import annotations

import logging
from typing import Optional

from trader.core.events import BarEvent, OrderEvent, Side
from trader.live.pretrade import PreTradeLimits, PreTradeRiskGate, RunCircuitBreaker
from trader.strategy.portfolio import FxRates, Portfolio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EOD unfilled policy
# ---------------------------------------------------------------------------
#
# For daily bars, residual unfilled orders are conceptually cancelled at EOD:
#   - Market orders are expected to fill within the same session.
#   - Limit orders that go unfilled are treated as expired at day-end.
# TODO: hook a real cancel API call here (e.g. VTTT1004U for overseas,
#       domestic equivalent for KOSPI) once live cancel is supported.
# Do NOT implement live cancel now — this constant records the policy intent.
EOD_UNFILLED_POLICY = "cancel"


def protective_limit_price(side: Side, last_close: float, band: float = 0.01) -> float:
    """Return a limit price with a protective band around last_close.

    BUY  → last_close * (1 + band)   # pay up to this much
    SELL → last_close * (1 - band)   # accept down to this much
    Rounded to 2 decimal places.
    """
    if side == Side.BUY:
        return round(last_close * (1.0 + band), 2)
    else:
        return round(last_close * (1.0 - band), 2)


class DailyActEngine:
    """Once-per-trading-day runner.

    Flow:
      1. Fetch account snapshot → build Portfolio.
      2. Fetch daily bars for every symbol.
      3. For each symbol's bars (ascending): warmup_bar on all but the last,
         then on_bar on the last (act only on the latest bar).
      4. dry_run=True  → return orders without submitting.
         dry_run=False → submit each order via kis with protective limit price,
                         skipping markets already recorded in ledger for today.

    Portfolio wiring:
      FusionEngine holds a `.portfolio` attribute set at construction time.
      DailyActEngine builds the Portfolio from the live snapshot and injects it
      directly via `strategy.portfolio = portfolio` before running any bars.
      This is the simplest zero-ceremony approach: no extra setter needed,
      the attribute is public and writable.
    """

    def __init__(
        self,
        kis_client,
        strategy,
        fx: FxRates,
        symbols: list[tuple[str, str, str]],
        *,
        band: float = 0.01,
        dry_run: bool = True,
        ledger=None,
        max_staleness_days: int = 4,
        journal=None,
        run_id: str | None = None,
        gate: PreTradeRiskGate | None = None,
        breaker: RunCircuitBreaker | None = None,
        submitter=None,
        killswitch=None,
        monitor=None,
    ):
        self.kis = kis_client
        self.strategy = strategy
        self.fx = fx
        self.symbols = symbols
        self.band = band
        self.dry_run = dry_run
        self.ledger = ledger
        self.max_staleness_days = max_staleness_days
        self.journal = journal
        self.run_id = run_id
        # Pre-trade gate and circuit breaker.
        # None = caller did not opt in; checks are skipped (backward-compatible).
        # Pass explicit instances to activate.
        self.gate: PreTradeRiskGate | None = gate
        self.breaker: RunCircuitBreaker | None = breaker
        # P0 safety: resilient submitter, kill switch, monitor (all optional).
        # None = caller did not opt in; legacy path is preserved.
        self.submitter = submitter
        self.killswitch = killswitch
        self.monitor = monitor
        # Collect blocked orders for observability
        self.blocked: list[dict] = []

    def run(self) -> list[OrderEvent]:
        # ── Kill-switch check (live-only; dry_run path skips) ─────────────────
        if not self.dry_run and self.killswitch is not None:
            if self.killswitch.is_active():
                status = self.killswitch.status()
                reason = status.get("reason", "unknown")
                logger.warning(
                    "KillSwitch is ACTIVE — aborting live run. reason=%s", reason
                )
                if self.monitor is not None:
                    self.monitor.alert(
                        "CRITICAL",
                        "KILLSWITCH_ACTIVE_AT_START",
                        {"reason": reason, "source": status.get("source", "")},
                    )
                return []

        # ── 1. Account snapshot → Portfolio ──────────────────────────────────
        snapshot = self.kis.account_snapshot()
        portfolio = Portfolio.from_snapshot(snapshot, self.fx)
        self.strategy.portfolio = portfolio

        # ── 2. Fetch bars for all symbols ────────────────────────────────────
        # all_bars: list of (market_str, ticker_str, bar)
        all_bars: list[tuple[str, str, BarEvent]] = []
        for ticker, market, currency in self.symbols:
            bars = self.kis.daily_bars(ticker, market, currency)
            for bar in bars:
                all_bars.append((market, ticker, bar))

        # ── 3. Group by (market, ticker) ─────────────────────────────────────
        groups: dict[tuple[str, str], list[BarEvent]] = {}
        for market, ticker, bar in all_bars:
            key = (market, ticker)
            groups.setdefault(key, []).append(bar)

        # Sort bars within each group ascending by ts (already sorted by
        # daily_bars, but be defensive).
        for key in groups:
            groups[key].sort(key=lambda b: b.ts)

        # ── Staleness guard ──────────────────────────────────────────────────
        # Derive a reference date from data, not the system clock:
        # use the maximum latest-bar date across all symbols.  A symbol whose
        # latest bar is more than max_staleness_days older than that reference
        # is considered stale (holiday / market closed) and is skipped for
        # action (warmup-only) to avoid acting on yesterday's close.
        latest_bar_per_group: dict[tuple[str, str], BarEvent] = {
            key: groups[key][-1] for key in groups if groups[key]
        }
        if latest_bar_per_group:
            reference_date = max(
                b.ts.date() for b in latest_bar_per_group.values()
            )
        else:
            reference_date = None

        # Process symbols in deterministic order: by (market, ticker).
        # Within processing, bars are sorted ascending so warmup sees history
        # before the latest bar triggers a decision.
        orders: list[OrderEvent] = []
        # Track the latest bar per symbol key for use in submission step.
        latest_bars: dict[tuple[str, str], BarEvent] = {}
        for key in sorted(groups.keys()):
            bars = groups[key]
            if not bars:
                continue
            *warmup_bars, latest_bar = bars
            latest_bars[key] = latest_bar

            # Staleness check: compare this symbol's latest bar date to reference
            is_stale = False
            if reference_date is not None:
                bar_date = latest_bar.ts.date()
                staleness = (reference_date - bar_date).days
                if staleness > self.max_staleness_days:
                    logger.info(
                        "Skipping %s/%s — latest bar %s is %d days behind "
                        "reference %s (max_staleness_days=%d)",
                        key[0], key[1], bar_date, staleness,
                        reference_date, self.max_staleness_days,
                    )
                    is_stale = True

            for bar in warmup_bars:
                portfolio.mark(bar)
                self.strategy.warmup_bar(bar)

            if is_stale:
                # Warm up on the latest bar too so indicators stay consistent,
                # but do NOT act (no on_bar call).
                portfolio.mark(latest_bar)
                self.strategy.warmup_bar(latest_bar)
            else:
                portfolio.mark(latest_bar)
                signals = self.strategy.observe_bar(latest_bar)
                combined = self.strategy.combined_score(signals)
                new_orders = self.strategy.decide_orders(latest_bar, signals)
                orders.extend(new_orders)
                if self.journal is not None and self.run_id is not None:
                    from trader.live.journal import build_record
                    rec = build_record(
                        engine=getattr(self.strategy, "name", "fusion_v1"),
                        run_id=self.run_id,
                        bar=latest_bar,
                        signals=signals,
                        combined=combined,
                        target_weight=combined,
                        orders=new_orders,
                    )
                    self.journal.append(rec)

        # ── 4. Submit or dry-run ──────────────────────────────────────────────
        if self.dry_run:
            # In dry-run, report which orders would be blocked by the gate
            # (informational only — does not prevent returning orders)
            if self.gate is not None:
                for order in orders:
                    sym_key = (order.symbol.market.value, order.symbol.ticker)
                    sym_latest = latest_bars.get(sym_key)
                    last_close = sym_latest.close if sym_latest else (order.limit_price or 0.0)
                    result = self.gate.check_order(
                        order,
                        decision_price=last_close,
                        last_close=last_close,
                        portfolio=portfolio,
                    )
                    if not result.approved:
                        logger.info(
                            "dry_run gate block: %s/%s reason=%s",
                            order.symbol.market.value, order.symbol.ticker, result.reason,
                        )
                        if self.monitor is not None:
                            self.monitor.alert(
                                "WARN",
                                "GATE_BLOCK",
                                {
                                    "ticker": order.symbol.ticker,
                                    "market": order.symbol.market.value,
                                    "side": order.side.value,
                                    "reason": result.reason,
                                    "dry_run": True,
                                },
                            )
            # Emit run-end INFO in dry-run
            if self.monitor is not None:
                self.monitor.alert(
                    "INFO",
                    "RUN_END",
                    {"mode": "dry_run", "orders_generated": len(orders)},
                )
            return orders

        # ── Live run: emit run-start INFO ─────────────────────────────────────
        if self.monitor is not None:
            self.monitor.alert(
                "INFO",
                "RUN_START",
                {"mode": "live", "orders_pending": len(orders)},
            )

        submitted: list[OrderEvent] = []
        for order in orders:
            market_str = order.symbol.market.value
            ticker = order.symbol.ticker
            sym_key = (market_str, ticker)

            # Resolve the latest bar for this specific symbol
            sym_latest = latest_bars.get(sym_key)
            trading_date = str(sym_latest.ts.date()) if sym_latest else ""

            # Idempotency: skip if ledger says we already submitted this ticker today
            if self.ledger is not None:
                if not self.ledger.acquire(self.kis.account, trading_date, market_str, ticker):
                    continue  # already submitted for this ticker today

            # Compute protective limit price from the last close for this symbol
            last_close = sym_latest.close if sym_latest else (order.limit_price or 0.0)
            limit = protective_limit_price(order.side, last_close, self.band)

            # ── Pre-trade risk gate (only when explicitly wired) ──────────────
            if self.gate is not None:
                gate_result = self.gate.check_order(
                    order,
                    decision_price=last_close,
                    last_close=last_close,
                    portfolio=portfolio,
                )
                if not gate_result.approved:
                    logger.warning(
                        "Pre-trade gate BLOCKED %s/%s side=%s qty=%d reason=%s",
                        market_str, ticker, order.side.value,
                        order.quantity, gate_result.reason,
                    )
                    self.blocked.append({
                        "order": order,
                        "reason": gate_result.reason,
                    })
                    if self.monitor is not None:
                        self.monitor.alert(
                            "WARN",
                            "GATE_BLOCK",
                            {
                                "ticker": ticker,
                                "market": market_str,
                                "side": order.side.value,
                                "reason": gate_result.reason,
                            },
                        )
                    continue

            # ── Circuit breaker (only when explicitly wired) ──────────────────
            if self.breaker is not None and not self.breaker.allow():
                logger.warning(
                    "Circuit breaker TRIPPED — skipping %s/%s (max_orders_per_run=%d reached)",
                    market_str, ticker, self.breaker._max,
                )
                self.blocked.append({
                    "order": order,
                    "reason": "CIRCUIT_BREAKER",
                })
                if self.monitor is not None:
                    self.monitor.alert(
                        "WARN",
                        "CIRCUIT_BREAKER_TRIP",
                        {
                            "ticker": ticker,
                            "market": market_str,
                            "max_orders_per_run": self.breaker._max,
                        },
                    )
                continue

            # ── Order submission ──────────────────────────────────────────────
            if self.submitter is not None:
                # Route through ResilientSubmitter
                result = self.submitter.submit(
                    ticker=ticker,
                    market=market_str,
                    side=order.side.value,
                    quantity=order.quantity,
                    price=limit,
                    order_type="00",  # limit
                )
                status = result["status"]

                if status == "SUBMITTED":
                    submitted.append(order)

                elif status == "REJECTED":
                    logger.warning(
                        "Order REJECTED %s/%s side=%s reason=%s",
                        market_str, ticker, order.side.value, result["reason"],
                    )
                    if self.monitor is not None:
                        self.monitor.alert(
                            "WARN",
                            "ORDER_REJECTED",
                            {
                                "ticker": ticker,
                                "market": market_str,
                                "side": order.side.value,
                                "reason": result["reason"],
                                "attempts": result["attempts"],
                            },
                        )
                    # REJECTED: log and continue (no portfolio change)

                elif status == "UNKNOWN":
                    logger.error(
                        "Order UNKNOWN state %s/%s side=%s — tripping kill switch. reason=%s",
                        market_str, ticker, order.side.value, result["reason"],
                    )
                    # Trip the kill switch to prevent further submissions
                    if self.killswitch is not None:
                        self.killswitch.trip(
                            reason="ORDER_UNKNOWN_STATE",
                            source="DailyActEngine",
                        )
                    if self.monitor is not None:
                        self.monitor.alert(
                            "CRITICAL",
                            "ORDER_UNKNOWN_STATE",
                            {
                                "ticker": ticker,
                                "market": market_str,
                                "side": order.side.value,
                                "reason": result["reason"],
                                "attempts": result["attempts"],
                            },
                        )
                    # Do NOT resubmit; stop processing further orders
                    break

            else:
                # Legacy path: no submitter wired — call kis directly
                self.kis.submit_order(
                    ticker=ticker,
                    market=market_str,
                    side=order.side.value,
                    quantity=order.quantity,
                    price=limit,
                    order_type="00",  # limit
                )
                submitted.append(order)

        # ── Live run: emit run-end INFO ───────────────────────────────────────
        if self.monitor is not None:
            self.monitor.alert(
                "INFO",
                "RUN_END",
                {"mode": "live", "orders_submitted": len(submitted)},
            )

        return submitted
