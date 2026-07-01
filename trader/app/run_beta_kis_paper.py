# trader/app/run_beta_kis_paper.py
"""PAPER — trade the defensive BETA strategy on the KIS paper account.

Holds ONE market ETF (KODEX 200, 069500) at the defensive exposure
(vol-target + trend cash-switch on the EW-KOSPI index), rest in cash. Rebalances
daily but only when the weight gap exceeds a band (avoids churn). This makes the
KIS *paper* account actually trade the sensible strategy, accumulating a real
fill-based track record — vs the no-edge technical strategy that mostly HOLDs.

Safety: dry-run by default (prints the order). --live submits to the KIS PAPER
endpoint only (build_kis_client targets PAPER_BASE), gated by live_allowed()
(--live + kill-switch-clear + LIVE_TRADING_ENABLED + account allowlist) and the
pre-trade risk gate. NEVER reaches a real-money endpoint.

Usage:
    python -m trader.app.run_beta_kis_paper                 # dry-run
    python -m trader.app.run_beta_kis_paper --live          # submit paper order
"""
from __future__ import annotations

import argparse
import glob
import os
from datetime import datetime, timezone

from trader.app.run_daily import build_kis_client, live_allowed, _load_dotenv
from trader.data.storage import load_bars
from trader.live import heartbeat as hb
from trader.research.beta_game import ew_daily_returns
from trader.strategy.beta_allocator import latest_exposure, rebalance_order

ETF_TICKER = "069500"   # KODEX 200 (KOSPI index ETF)
ETF_MARKET = "KOSPI"
TRACK_PATH = "beta_kis_track.jsonl"


def _ew_kospi_returns(data_dir: str = "research_data") -> list[float]:
    panel = {}
    for p in sorted(glob.glob(os.path.join(data_dir, "KOSPI_*.parquet"))):
        b = load_bars(p)
        if b:
            panel[os.path.basename(p)[6:-8]] = b
    return [r for _d, r in ew_daily_returns(panel)]


def _etf_price(kis) -> float:
    """KODEX 200 price for sizing: use the account mark if held, else yfinance."""
    snap = kis.account_snapshot()
    mark = snap["marks"].get((ETF_MARKET, ETF_TICKER))
    if mark and mark > 0:
        return float(mark)
    from trader.data.research_provider import _yf_download_normalize
    rows = _yf_download_normalize(f"{ETF_TICKER}.KS", years=1, auto_adjust=False)
    return float(rows[-1]["close"]) if rows else 0.0


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="[PAPER] defensive beta on KIS paper account")
    p.add_argument("--live", action="store_true", help="submit the paper order (default: dry-run)")
    p.add_argument("--target-vol", type=float, default=0.15)
    p.add_argument("--trend-window", type=int, default=200)
    p.add_argument("--rebalance-band", type=float, default=0.05)
    args = p.parse_args(argv)

    if "KIS_APP_KEY" not in os.environ:
        _load_dotenv()
    kis = build_kis_client()  # PAPER_BASE only

    snap = kis.account_snapshot()
    cash = snap["cash_krw"]
    current_shares = int(snap["positions"].get((ETF_MARKET, ETF_TICKER), 0))
    price = _etf_price(kis)
    rets = _ew_kospi_returns()
    exposure = latest_exposure(rets, target_vol=args.target_vol,
                               trend_window=args.trend_window or None)
    order = rebalance_order(exposure, price, cash, current_shares,
                            rebalance_band=args.rebalance_band)

    print("=" * 60)
    print(f"[BETA KIS PAPER] {'LIVE(paper)' if args.live else 'DRY-RUN'}")
    print(f"  cash={cash:,.0f} KRW | KODEX200 shares={current_shares} @ {price:,.0f}")
    print(f"  index days={len(rets)} | exposure={exposure:.2f} "
          f"(target_vol={args.target_vol:.0%}, trend={args.trend_window})")
    print(f"  decision: {order['side']} {order['qty']} 069500  "
          f"(cur_w={order.get('cur_weight',0):.2f} → tgt_w={order.get('tgt_weight',0):.2f}, "
          f"{order['reason']})")

    submitted = None
    if args.live and order["side"] != "HOLD":
        allowed, reason = live_allowed(True, dict(os.environ), kis.account)
        if not allowed:
            print(f"  [LIVE GATE REFUSED] {reason} → not submitting")
        else:
            odno = kis.submit_order(ETF_TICKER, ETF_MARKET, order["side"],
                                    order["qty"], price=0.0, order_type="01")
            submitted = odno
            print(f"  [LIVE] submitted {order['side']} {order['qty']} 069500 → ODNO {odno}")
    elif args.live:
        print("  [LIVE] nothing to do (HOLD)")

    _append_track({
        "as_of": datetime.now(tz=timezone.utc).isoformat(),
        "cash_krw": cash, "etf_shares": current_shares, "etf_price": price,
        "exposure": exposure, "side": order["side"], "qty": order["qty"],
        "reason": order["reason"], "submitted_odno": submitted, "live": args.live,
    })
    hb.record("beta_kis_paper", ts=datetime.now(tz=timezone.utc).isoformat())


def _append_track(rec: dict, path: str = TRACK_PATH) -> None:
    import json
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
