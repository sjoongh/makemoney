# trader/app/run_beta_kis_paper.py
"""PAPER — trade the defensive BETA strategy on the KIS paper account (KR + US).

Holds ONE market ETF per sleeve at the defensive exposure (vol-target + trend
cash-switch on that market's EW index), the rest in cash:
  KR sleeve  → KODEX 200 (069500), KOSPI, market order, prices in KRW
  US sleeve  → SPY,        NASDAQ, LIMIT order (US paper is limit-only), USD→KRW via FX

This makes the KIS paper account actually trade the sensible strategy (real
fills) instead of the no-edge technical one that mostly HOLDs. Sizing is done in
KRW throughout (SPY price converted at the live USD/KRW rate); ``--capital-frac``
splits equity when running both sleeves.

Safety: dry-run by default; --live submits to the KIS PAPER endpoint only,
gated by live_allowed() + kill switch; graceful on market-closed rejection.
NEVER reaches a real-money endpoint.

Usage:
    python -m trader.app.run_beta_kis_paper --market KR            # dry-run
    python -m trader.app.run_beta_kis_paper --market US --live     # submit paper
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timezone

from trader.app.run_daily import build_kis_client, live_allowed, _load_dotenv
from trader.data.storage import load_bars
from trader.live import heartbeat as hb
from trader.research.beta_game import ew_daily_returns
from trader.strategy.beta_allocator import latest_exposure, rebalance_order

TRACK_PATH = "beta_kis_track.jsonl"

MARKETS = {
    "KR": {"etf": "069500", "market": "KOSPI", "index": "KOSPI", "ccy": "KRW",
           "order_type": "01", "yf": "069500.KS"},   # KODEX 200, market order
    "US": {"etf": "SPY", "market": "NASDAQ", "index": "NASDAQ", "ccy": "USD",
           "order_type": "00", "yf": "SPY"},          # SPY, LIMIT order
}


def _index_returns(index_prefix: str, data_dir: str = "research_data") -> list[float]:
    panel = {}
    for p in sorted(glob.glob(os.path.join(data_dir, f"{index_prefix}_*.parquet"))):
        b = load_bars(p)
        if b:
            panel[os.path.basename(p)] = b
    return [r for _d, r in ew_daily_returns(panel)]


def _etf_native_price(cfg: dict) -> float:
    """Latest ETF price in its native currency (USD for SPY, KRW for KODEX)."""
    from trader.data.research_provider import _yf_download_normalize
    rows = _yf_download_normalize(cfg["yf"], years=1, auto_adjust=False)
    return float(rows[-1]["close"]) if rows else 0.0


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="[PAPER] defensive beta on KIS paper (KR/US)")
    p.add_argument("--market", choices=["KR", "US"], default="KR")
    p.add_argument("--live", action="store_true", help="submit the paper order (default dry-run)")
    p.add_argument("--target-vol", type=float, default=0.15)
    p.add_argument("--trend-window", type=int, default=200)
    p.add_argument("--rebalance-band", type=float, default=0.05)
    p.add_argument("--capital-frac", type=float, default=1.0,
                   help="fraction of equity this sleeve may use (0.5 when running both)")
    args = p.parse_args(argv)
    cfg = MARKETS[args.market]

    if "KIS_APP_KEY" not in os.environ:
        _load_dotenv()
    kis = build_kis_client()  # PAPER_BASE only

    snap = kis.account_snapshot()
    cash_krw = snap["cash_krw"]
    current_shares = int(snap["positions"].get((cfg["market"], cfg["etf"]), 0))

    native_price = _etf_native_price(cfg)
    fx = kis.usd_krw_rate() if cfg["ccy"] == "USD" else 1.0
    price_krw = native_price * fx  # sizing currency = KRW throughout

    rets = _index_returns(cfg["index"])
    exposure = latest_exposure(rets, target_vol=args.target_vol,
                               trend_window=args.trend_window or None)
    # capital fraction caps how much of equity this sleeve deploys
    sleeve_exposure = exposure * args.capital_frac
    order = rebalance_order(sleeve_exposure, price_krw, cash_krw, current_shares,
                            rebalance_band=args.rebalance_band)

    print("=" * 62)
    print(f"[BETA KIS PAPER · {args.market}] {'LIVE(paper)' if args.live else 'DRY-RUN'}  ETF={cfg['etf']}")
    print(f"  cash={cash_krw:,.0f} KRW | {cfg['etf']} shares={current_shares} @ "
          f"{native_price:,.2f} {cfg['ccy']} (={price_krw:,.0f} KRW, fx={fx:,.1f})")
    print(f"  index days={len(rets)} | exposure={exposure:.2f}×frac{args.capital_frac:g}="
          f"{sleeve_exposure:.2f} (tvol={args.target_vol:.0%}, trend={args.trend_window})")
    print(f"  decision: {order['side']} {order['qty']} {cfg['etf']}  "
          f"(w {order.get('cur_weight',0):.2f}→{order.get('tgt_weight',0):.2f}, {order['reason']})")

    submitted = None
    if args.live and order["side"] != "HOLD":
        allowed, reason = live_allowed(True, dict(os.environ), kis.account)
        if not allowed:
            print(f"  [LIVE GATE REFUSED] {reason}")
        else:
            # US paper is limit-only: price the limit through market to fill.
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
            "as_of": datetime.now(tz=timezone.utc).isoformat(), "market": args.market,
            "etf": cfg["etf"], "cash_krw": cash_krw, "shares": current_shares,
            "native_price": native_price, "fx": fx, "exposure": exposure,
            "capital_frac": args.capital_frac, "side": order["side"], "qty": order["qty"],
            "reason": order["reason"], "submitted_odno": submitted, "live": args.live,
        }, ensure_ascii=False) + "\n")
    hb.record(f"beta_kis_{args.market.lower()}", ts=datetime.now(tz=timezone.utc).isoformat())


if __name__ == "__main__":
    main()
