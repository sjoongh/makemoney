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

Live-trading hard gate (ALL three conditions must be satisfied):
  1. --live flag passed on the command line.
  2. Environment variable LIVE_TRADING_ENABLED=true (case-insensitive).
  3. The configured KIS_ACCOUNT is listed in KIS_LIVE_ACCOUNT_ALLOWLIST
     (comma-separated env var).

If --live is passed but the gate is not fully satisfied, the runner falls
back to dry-run and prints a clear refusal message.

Additionally, if the durable KillSwitch is active, the runner refuses to
run live (falls back to dry-run) and prints the reason.
"""
from __future__ import annotations

import argparse
import os
import sys

import httpx

from trader.app.config import AppConfig
from trader.live.daily import DailyActEngine
from trader.live.journal import SignalJournal
from trader.live.ledger import RunLedger
from trader.live.killswitch import KillSwitch
from trader.live.monitor import LogAlertSink, Monitor
from trader.live.order_exec import ResilientSubmitter
from trader.live.pretrade import PreTradeLimits, PreTradeRiskGate, RunCircuitBreaker
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


def filter_symbols_by_market(
    symbols: list[tuple[str, str, str]], market: str
) -> list[tuple[str, str, str]]:
    """Return only the symbols whose market field matches `market`.

    market="ALL" returns the full list unchanged.
    Any other value filters to exact string match on the second element.
    Unknown market names (no match) return an empty list.
    """
    if market == "ALL":
        return list(symbols)
    return [(t, m, c) for t, m, c in symbols if m == market]


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


# ---------------------------------------------------------------------------
# Hard live-trading gate (pure function — fully unit-testable)
# ---------------------------------------------------------------------------

def live_allowed(
    args_live: bool,
    env: dict,
    account: str,
    killswitch_path: str = ".kill_switch.json",
) -> tuple[bool, str]:
    """Determine whether live order submission is permitted.

    This is a pure-logic function (reads env dict + disk via KillSwitch)
    with no side-effects beyond the KillSwitch file read.

    Args:
        args_live: True if --live was passed on the command line.
        env: Mapping of environment variables (typically ``os.environ``).
        account: The configured KIS account number.
        killswitch_path: Path to the kill-switch JSON file.

    Returns:
        (allowed: bool, reason: str)
          allowed=True  → live submission is permitted; reason is "".
          allowed=False → blocked; reason describes WHY.
    """
    if not args_live:
        return False, "dry-run mode (--live not passed)"

    # Check kill switch first (fastest block, no env check needed)
    ks = KillSwitch(path=killswitch_path)
    if ks.is_active():
        status = ks.status()
        return False, f"kill switch active: {status.get('reason', 'unknown reason')}"

    # LIVE_TRADING_ENABLED must be exactly "true" (case-insensitive)
    enabled_raw = env.get("LIVE_TRADING_ENABLED", "")
    if enabled_raw.strip().lower() != "true":
        return False, (
            "LIVE_TRADING_ENABLED env var is not set to 'true' "
            f"(got: {enabled_raw!r})"
        )

    # Account allowlist
    allowlist_raw = env.get("KIS_LIVE_ACCOUNT_ALLOWLIST", "")
    allowlist = [a.strip() for a in allowlist_raw.split(",") if a.strip()]
    if not allowlist:
        return False, (
            "KIS_LIVE_ACCOUNT_ALLOWLIST env var is empty or not set; "
            "add the account number to permit live trading"
        )
    if account not in allowlist:
        return False, (
            f"account {account!r} is not in KIS_LIVE_ACCOUNT_ALLOWLIST "
            f"(allowlist: {allowlist})"
        )

    return True, ""


# ---------------------------------------------------------------------------
# KisClient factory
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(dry_run: bool = True, market: str = "ALL") -> None:
    symbols = filter_symbols_by_market(SYMBOLS, market)
    if not symbols:
        print(f"No symbols match market={market!r}. Exiting.")
        return

    # ── Resolve effective dry_run after gate check ────────────────────────
    # dry_run=False means --live was passed; re-evaluate through the hard gate.
    if not dry_run:
        if "KIS_APP_KEY" not in os.environ:
            _load_dotenv()
        cfg = AppConfig.from_env()
        allowed, gate_reason = live_allowed(
            args_live=True,
            env=dict(os.environ),
            account=cfg.kis_account,
        )
        if not allowed:
            print(
                f"\n[LIVE GATE REFUSED] Live submission blocked: {gate_reason}"
            )
            print("[LIVE GATE REFUSED] Falling back to DRY-RUN mode.\n")
            dry_run = True
        else:
            print("\n[LIVE GATE PASSED] All live-trading conditions satisfied.")
    else:
        print("\n[MODE] DRY-RUN (no gate envs required)")

    # ── Startup banner ────────────────────────────────────────────────────
    ks = KillSwitch()
    ks_status = ks.status()
    kill_active = ks_status.get("active", False)

    print("=" * 60)
    print(f"  Mode            : {'LIVE' if not dry_run else 'DRY-RUN'}")
    print(f"  Market filter   : {market}")
    print(f"  Symbols         : {symbols}")
    print(f"  Kill switch     : {'ACTIVE — ' + ks_status.get('reason', '') if kill_active else 'inactive'}")
    ks_source = ks_status.get('source', '')
    if kill_active and ks_source:
        print(f"  Kill switch src : {ks_source}")
    print(f"  LIVE gate env   : LIVE_TRADING_ENABLED={os.environ.get('LIVE_TRADING_ENABLED', '(not set)')!r}")
    print(f"  Allowlist       : KIS_LIVE_ACCOUNT_ALLOWLIST={os.environ.get('KIS_LIVE_ACCOUNT_ALLOWLIST', '(not set)')!r}")
    print("=" * 60)

    print(f"\nMarket filter: {market}  →  symbols: {symbols}")
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

    journal = SignalJournal(root="paper_forward")
    from datetime import date
    run_id = f"run-{date.today().isoformat()}"

    # Wire PreTradeRiskGate explicitly so the entrypoint shows active limits.
    limits = PreTradeLimits()
    gate = PreTradeRiskGate(limits, fx)
    breaker = RunCircuitBreaker(limits.max_orders_per_run)

    print(
        f"\n[PreTradeRiskGate] active limits: "
        f"max_order_notional_krw={limits.max_order_notional_krw:,.0f} "
        f"max_position_weight={limits.max_position_weight:.0%} "
        f"fat_finger_qty={limits.fat_finger_qty:,} "
        f"max_orders_per_run={limits.max_orders_per_run}"
    )

    # ── P0 safety components ──────────────────────────────────────────────
    monitor = Monitor([LogAlertSink()])
    if not dry_run:
        submitter = ResilientSubmitter(kis)
        killswitch = KillSwitch()
        print(
            "\n[P0 Safety] ResilientSubmitter + KillSwitch + Monitor(LogAlertSink) ACTIVE"
        )
    else:
        submitter = None
        killswitch = None
        print(
            "\n[P0 Safety] Monitor(LogAlertSink) active (dry-run: no submitter/killswitch)"
        )

    engine = DailyActEngine(
        kis_client=kis,
        strategy=strategy,
        fx=fx,
        symbols=symbols,
        band=0.01,
        dry_run=dry_run,
        ledger=ledger,
        journal=journal,
        run_id=run_id,
        gate=gate,
        breaker=breaker,
        submitter=submitter,
        killswitch=killswitch,
        monitor=monitor,
    )

    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"\nRunning DailyActEngine [{mode}] for symbols: {symbols}")
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
    parser.add_argument(
        "--market",
        choices=["NASDAQ", "KOSPI", "ALL"],
        default="ALL",
        help="Filter symbols to this market (default: ALL)",
    )
    args = parser.parse_args()
    main(dry_run=not args.live, market=args.market)
