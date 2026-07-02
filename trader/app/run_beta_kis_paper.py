# trader/app/run_beta_kis_paper.py
"""PAPER — trade the defensive BETA strategy on the KIS paper account (KR + US).

Holds ONE market ETF per sleeve at the defensive exposure (vol-target + trend
cash-switch on that market's EW index), the rest in cash:
  KR sleeve  → KODEX 200 (069500), KOSPI, market order, prices in KRW
  US sleeve  → SPY,        NASDAQ, LIMIT order (US paper is limit-only), USD→KRW via FX

Hardened after the 2026-07-02 multi-agent audit:
  - SHARED EQUITY sizing: equity = domestic net asset − overseas purchase cost
    + overseas position value×FX, passed explicitly to rebalance_order — the old
    per-sleeve cash+own-shares equity double-counted and compounded over-buying.
  - IDEMPOTENCY: refuses a second live submission for the same market on the
    same KST day (the track file is the ledger).
  - DATA GATES: index returns use a coverage floor (≥50% of names) and exclude
    today's partial bar; the run ABORTS (no trade) if the newest usable index
    date is older than MAX_DATA_AGE_DAYS.
  - FX GATE: aborts if the live USD/KRW rate cannot be fetched (no silent 1380).
  - PRE-TRADE CAPS: per-order notional cap, fat-finger qty cap, max target
    weight — refuses rather than submits.

Safety: dry-run by default; --live submits to the KIS PAPER endpoint only,
gated by live_allowed() + kill switch. NEVER reaches a real-money endpoint.

Usage:
    python -m trader.app.run_beta_kis_paper --market KR            # dry-run
    python -m trader.app.run_beta_kis_paper --market US --live     # submit paper
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timedelta, timezone

from trader.app.run_daily import build_kis_client, live_allowed, _load_dotenv
from trader.data.storage import load_bars
from trader.live import heartbeat as hb
from trader.strategy.beta_allocator import (
    latest_exposure,
    rebalance_order,
    robust_index_returns,
)

TRACK_PATH = "beta_kis_track.jsonl"
KST = timezone(timedelta(hours=9))

MARKETS = {
    "KR": {"etf": "069500", "market": "KOSPI", "index": "KOSPI", "ccy": "KRW",
           "order_type": "01", "yf": "069500.KS"},   # KODEX 200, market order
    "US": {"etf": "SPY", "market": "NASDAQ", "index": "NASDAQ", "ccy": "USD",
           "order_type": "00", "yf": "SPY"},          # SPY, LIMIT order
}

# Pre-trade caps (paper-sane defaults; env-tunable)
MAX_ORDER_NOTIONAL_KRW = float(os.environ.get("MAX_ORDER_NOTIONAL_KRW", 60_000_000))
FAT_FINGER_QTY = 10_000
MAX_TARGET_WEIGHT = 0.65          # per sleeve, of TRUE equity
MAX_DATA_AGE_DAYS = 7             # newest usable index date must be this fresh
MIN_COVERAGE = 0.5


def _load_panel(index_prefix: str, data_dir: str = "research_data") -> dict:
    panel = {}
    for p in sorted(glob.glob(os.path.join(data_dir, f"{index_prefix}_*.parquet"))):
        b = load_bars(p)
        if b:
            panel[os.path.basename(p)] = b
    return panel


def _etf_native_price(cfg: dict) -> float:
    from trader.data.research_provider import _yf_download_normalize
    rows = _yf_download_normalize(cfg["yf"], years=1, auto_adjust=False)
    return float(rows[-1]["close"]) if rows else 0.0


def _already_submitted_today(market: str, today_kst: str, path: str = TRACK_PATH) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (r.get("market") == market and r.get("live") and r.get("submitted_odno")
                    and r.get("kst_date") == today_kst):
                return True
    return False


def _total_equity_krw(snap: dict, usd_fx: float) -> float:
    """True shared account equity: domestic net asset − phantom-funded overseas
    cost + overseas position value at current marks × USD/KRW.

    ``usd_fx`` is the USD→KRW rate and is required whenever the account holds
    NASDAQ positions — regardless of which sleeve is being run (the KR sleeve
    still needs the SPY value in KRW to know true equity)."""
    ovr_val_krw = sum(
        qty * snap["marks"].get((mkt, tk), 0.0) * usd_fx
        for (mkt, tk), qty in snap["positions"].items()
        if mkt == "NASDAQ"
    )
    return snap["nass_krw"] - snap["ovr_purchase_krw"] + ovr_val_krw


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="[PAPER] defensive beta on KIS paper (KR/US)")
    p.add_argument("--market", choices=["KR", "US"], default="KR")
    p.add_argument("--live", action="store_true", help="submit the paper order (default dry-run)")
    p.add_argument("--target-vol", type=float, default=0.15)
    p.add_argument("--trend-window", type=int, default=200)
    p.add_argument("--rebalance-band", type=float, default=0.05)
    p.add_argument("--capital-frac", type=float, default=0.5,
                   help="fraction of TRUE equity this sleeve may target")
    p.add_argument("--force", action="store_true",
                   help="bypass the same-day idempotency guard (manual use only)")
    args = p.parse_args(argv)
    cfg = MARKETS[args.market]

    now_kst = datetime.now(tz=KST)
    today_kst = now_kst.date()

    print("=" * 62)
    print(f"[BETA KIS PAPER · {args.market}] {'LIVE(paper)' if args.live else 'DRY-RUN'}  "
          f"ETF={cfg['etf']}  {now_kst:%Y-%m-%d %H:%M} KST")

    # ── Idempotency: one live submission per market per KST day ──────────
    if args.live and not args.force and _already_submitted_today(args.market, today_kst.isoformat()):
        print("  [SKIP] already submitted a live order for this market today "
              "(idempotency guard; --force to override)")
        return 0

    if "KIS_APP_KEY" not in os.environ:
        _load_dotenv()
    kis = build_kis_client()  # PAPER_BASE only

    snap = kis.account_snapshot()
    current_shares = int(snap["positions"].get((cfg["market"], cfg["etf"]), 0))
    has_us_positions = any(mkt == "NASDAQ" for (mkt, _tk) in snap["positions"])

    # ── FX gate (no silent 1380 fallback) ─────────────────────────────────
    # USD/KRW is needed to PRICE a USD sleeve AND to VALUE any NASDAQ position
    # for true equity — even when running the KR sleeve.
    usd_fx = 1.0
    if cfg["ccy"] == "USD" or has_us_positions:
        usd_fx = kis.usd_krw_rate(default=-1.0)
        if usd_fx <= 0:
            print("  [ABORT] live USD/KRW rate unavailable — refusing to size blind")
            return 1

    equity_krw = _total_equity_krw(snap, usd_fx)
    cash_krw = snap["cash_krw"]

    fx = usd_fx if cfg["ccy"] == "USD" else 1.0   # ETF pricing fx
    native_price = _etf_native_price(cfg)
    price_krw = native_price * fx

    # ── Index signal with coverage floor + partial-bar exclusion + recency ─
    panel = _load_panel(cfg["index"])
    dated = robust_index_returns(panel, min_coverage=MIN_COVERAGE, exclude_from=today_kst)
    if not dated:
        print("  [ABORT] no usable index data")
        return 1
    last_data_date = dated[-1][0]
    age = (today_kst - last_data_date).days
    if age > MAX_DATA_AGE_DAYS:
        print(f"  [ABORT] index data stale: newest usable date {last_data_date} "
              f"({age}d old > {MAX_DATA_AGE_DAYS}d) — refusing to trade on stale data")
        return 1
    rets = [r for _d, r in dated]

    exposure = latest_exposure(rets, target_vol=args.target_vol,
                               trend_window=args.trend_window or None)
    sleeve_exposure = exposure * args.capital_frac
    order = rebalance_order(sleeve_exposure, price_krw, cash_krw, current_shares,
                            equity_krw=equity_krw, rebalance_band=args.rebalance_band)

    print(f"  equity={equity_krw:,.0f} KRW (nass {snap['nass_krw']:,.0f} − ovr_cost "
          f"{snap['ovr_purchase_krw']:,.0f} + ovr_val) | cash={cash_krw:,.0f}")
    print(f"  {cfg['etf']} shares={current_shares} @ {native_price:,.2f} {cfg['ccy']} "
          f"(={price_krw:,.0f} KRW, fx={fx:,.1f})")
    print(f"  index: {len(rets)} usable days, newest {last_data_date} ({age}d old)")
    print(f"  exposure={exposure:.2f}×frac{args.capital_frac:g}={sleeve_exposure:.2f} "
          f"(tvol={args.target_vol:.0%}, trend={args.trend_window})")
    print(f"  decision: {order['side']} {order['qty']} {cfg['etf']}  "
          f"(w {order.get('cur_weight', 0):.2f}→{order.get('tgt_weight', 0):.2f}, {order['reason']})")

    # ── Pre-trade caps ────────────────────────────────────────────────────
    if order["side"] != "HOLD":
        notional = order["qty"] * price_krw
        tgt_w = order.get("tgt_weight", 0.0)
        if order["qty"] > FAT_FINGER_QTY:
            print(f"  [REFUSE] qty {order['qty']} > fat-finger cap {FAT_FINGER_QTY}")
            return 1
        if notional > MAX_ORDER_NOTIONAL_KRW:
            print(f"  [REFUSE] notional {notional:,.0f} > cap {MAX_ORDER_NOTIONAL_KRW:,.0f}")
            return 1
        if order["side"] == "BUY" and tgt_w > MAX_TARGET_WEIGHT:
            print(f"  [REFUSE] target weight {tgt_w:.2f} > cap {MAX_TARGET_WEIGHT}")
            return 1

    submitted = None
    if args.live and order["side"] != "HOLD":
        allowed, reason = live_allowed(True, dict(os.environ), kis.account)
        if not allowed:
            print(f"  [LIVE GATE REFUSED] {reason}")
        else:
            if cfg["ccy"] == "USD":
                limit = native_price * (1.01 if order["side"] == "BUY" else 0.99)
            else:
                limit = 0.0  # KOSPI market order
            try:
                odno = kis.submit_order(cfg["etf"], cfg["market"], order["side"],
                                        order["qty"], price=round(limit, 2),
                                        order_type=cfg["order_type"])
                submitted = odno
                print(f"  [LIVE] submitted {order['side']} {order['qty']} {cfg['etf']} → ODNO {odno}")
            except RuntimeError as exc:
                print(f"  [LIVE] submit not accepted: {exc}")
    elif args.live:
        print("  [LIVE] nothing to do (HOLD)")

    with open(TRACK_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "as_of": datetime.now(tz=timezone.utc).isoformat(),
            "kst_date": today_kst.isoformat(), "market": args.market,
            "etf": cfg["etf"], "cash_krw": cash_krw, "equity_krw": equity_krw,
            "shares": current_shares, "native_price": native_price, "fx": fx,
            "exposure": exposure, "capital_frac": args.capital_frac,
            "index_newest": last_data_date.isoformat(), "index_days": len(rets),
            "side": order["side"], "qty": order["qty"], "reason": order["reason"],
            "submitted_odno": submitted, "live": args.live,
        }, ensure_ascii=False) + "\n")
    hb.record(f"beta_kis_{args.market.lower()}", ts=datetime.now(tz=timezone.utc).isoformat())
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
