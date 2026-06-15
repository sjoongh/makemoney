# trader/app/run_daily.py
"""Once-per-trading-day runner.

Usage (dry-run, default — safe when markets are closed):
    python -m trader.app.run_daily

Usage (live — actually submits orders):
    python -m trader.app.run_daily --live

The runner:
  1. Loads credentials from .env (paper trading).
  2. Snapshots the real KIS account.
  3. Fetches daily bars for each symbol.
  4. Warms up FusionEngine indicators on all historical bars.
  5. Acts (decides orders) only on the latest bar.
  6. dry_run=True  → prints the orders it WOULD place, submits nothing.
     dry_run=False → submits limit orders with protective band, guarded by ledger.
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx

from trader.app.config import AppConfig
from trader.live.daily import DailyActEngine
from trader.live.ledger import RunLedger
from trader.signals.technical import TechnicalSignalSource  # kept for parity tests
from trader.signals.technical_indicator_source import TechnicalIndicatorSource
from trader.signals.indicators import (
    MovingAverageCross,
    RsiReversion,
    MacdTrend,
    BollingerReversion,
)
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.order_factory import OrderFactory
from trader.strategy.portfolio import FxRates, Portfolio
from trader.strategy.risk import RiskManager

PAPER_BASE = "https://openapivts.koreainvestment.com:29443"

SYMBOLS = [
    ("AAPL", "NASDAQ", "USD"),
    ("005930", "KOSPI", "KRW"),
]


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader — sets missing keys into os.environ, no extra deps."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def build_kis_client():
    """Build a live KisClient from environment / .env."""
    from trader.execution.kis_client import KisClient

    if "KIS_APP_KEY" not in os.environ:
        _load_dotenv()
    cfg = AppConfig.from_env()
    http = httpx.Client(base_url=PAPER_BASE, timeout=30)
    return KisClient(
        http,
        cfg.kis_app_key,
        cfg.kis_app_secret,
        cfg.kis_account,
        paper=cfg.paper,
        min_interval=1.0,  # conservative throttle for daily runner
    )


def main(dry_run: bool = True) -> None:
    kis = build_kis_client()

    # Fetch live USD/KRW rate via VTRP6504R; falls back to 1380.0 if unavailable.
    usd_rate = kis.usd_krw_rate(default=1380.0)
    fx = FxRates({"USD": usd_rate, "KRW": 1.0})
    print(f"FX rate: 1 USD = {usd_rate:,.2f} KRW (live via VTRP6504R, fallback=1380.0)")

    # Snapshot to learn current equity before building the portfolio.
    # DailyActEngine.run() will re-snapshot internally; this call is just
    # for the printed header.
    print("Fetching account snapshot …")
    snapshot = kis.account_snapshot()
    print(f"  cash_krw  : {snapshot['cash_krw']:,.0f} KRW")
    print(f"  positions : {snapshot['positions']}")
    print(f"  marks     : {snapshot['marks']}")

    # Build a throw-away portfolio + strategy (DailyActEngine will rebuild
    # from snapshot internally; these are just to satisfy constructor types).
    pf = Portfolio({"KRW": snapshot["cash_krw"]}, fx)
    sources = [
        TechnicalIndicatorSource(name="technical.ma_10_30",  indicator=MovingAverageCross(10, 30)),
        TechnicalIndicatorSource(name="technical.rsi_14",    indicator=RsiReversion(14, 30, 70)),
        TechnicalIndicatorSource(name="technical.macd",      indicator=MacdTrend(12, 26, 9)),
        TechnicalIndicatorSource(name="technical.boll_20_2", indicator=BollingerReversion(20, 2.0)),
    ]
    strategy = FusionEngine(
        signal_sources=sources,
        portfolio=pf,
        risk_manager=RiskManager(max_symbol_weight=0.3),
        order_factory=OrderFactory(),
        enter_threshold=0.35,
        source_weight={
            "technical.ma_10_30":  0.30,
            "technical.rsi_14":    0.20,
            "technical.macd":      0.30,
            "technical.boll_20_2": 0.20,
        },
    )

    ledger = RunLedger() if not dry_run else None

    engine = DailyActEngine(
        kis_client=kis,
        strategy=strategy,
        fx=fx,
        symbols=SYMBOLS,
        band=0.01,
        dry_run=dry_run,
        ledger=ledger,
    )

    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"\nRunning DailyActEngine [{mode}] for symbols: {SYMBOLS}")
    orders = engine.run()

    print(f"\n=== Orders {'(would place)' if dry_run else '(submitted)'} ===")
    if not orders:
        print("  (none — indicators may not be warmed up yet, or no signal)")
    else:
        for o in orders:
            print(
                f"  {o.side.value:4s} {o.quantity:6d} {o.symbol.ticker}"
                f" [{o.symbol.market.value}]"
                f"  reason={o.reason}"
            )

    if dry_run:
        print("\n[DRY RUN] No orders were submitted. Pass --live to submit.")
    else:
        print(f"\n[LIVE] {len(orders)} order(s) submitted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily KIS paper-trading runner")
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Actually submit orders (default: dry-run only)",
    )
    args = parser.parse_args()
    main(dry_run=not args.live)
