# trader/live/daily.py
"""Daily once-per-bar runner: warm up indicators on history, act only on the latest bar."""
from __future__ import annotations

import logging
from typing import Optional

from trader.core.events import BarEvent, OrderEvent, Side
from trader.strategy.portfolio import FxRates, Portfolio

logger = logging.getLogger(__name__)


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
    ):
        self.kis = kis_client
        self.strategy = strategy
        self.fx = fx
        self.symbols = symbols
        self.band = band
        self.dry_run = dry_run
        self.ledger = ledger
        self.max_staleness_days = max_staleness_days

    def run(self) -> list[OrderEvent]:
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
                orders.extend(self.strategy.on_bar(latest_bar))

        # ── 4. Submit or dry-run ──────────────────────────────────────────────
        if self.dry_run:
            return orders

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

            self.kis.submit_order(
                ticker=ticker,
                market=market_str,
                side=order.side.value,
                quantity=order.quantity,
                price=limit,
                order_type="00",  # limit
            )
            submitted.append(order)

        return submitted
