# trader/live/daily.py
"""Daily once-per-bar runner: warm up indicators on history, act only on the latest bar."""
from __future__ import annotations

from typing import Optional

from trader.core.events import BarEvent, OrderEvent, Side
from trader.strategy.portfolio import FxRates, Portfolio


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
    ):
        self.kis = kis_client
        self.strategy = strategy
        self.fx = fx
        self.symbols = symbols
        self.band = band
        self.dry_run = dry_run
        self.ledger = ledger

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

        # Process symbols in deterministic order: by (market, ticker).
        # Within processing, bars are sorted ascending so warmup sees history
        # before the latest bar triggers a decision.
        orders: list[OrderEvent] = []
        for key in sorted(groups.keys()):
            bars = groups[key]
            if not bars:
                continue
            *warmup_bars, latest_bar = bars
            for bar in warmup_bars:
                portfolio.mark(bar)
                self.strategy.warmup_bar(bar)
            portfolio.mark(latest_bar)
            orders.extend(self.strategy.on_bar(latest_bar))

        # ── 4. Submit or dry-run ──────────────────────────────────────────────
        if self.dry_run:
            return orders

        submitted: list[OrderEvent] = []
        for order in orders:
            market_str = order.symbol.market.value
            ticker = order.symbol.ticker

            # Idempotency: skip if ledger says we already ran this market today
            if self.ledger is not None:
                trading_date = str(latest_bar.ts.date())  # type: ignore[possibly-undefined]
                if not self.ledger.acquire(self.kis.account, trading_date, market_str):
                    continue  # already submitted for this market today

            # Compute protective limit price from the last bar for this symbol
            sym_bars = groups.get((market_str, ticker), [])
            last_close = sym_bars[-1].close if sym_bars else order.limit_price or 0.0
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
