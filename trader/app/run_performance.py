# trader/app/run_performance.py
"""PAPER — live performance report for the defensive-beta paper account.

Answers "지금 성과 어때?" at any moment from REAL account state (KIS paper
positions + marks) and the clean-era track file — no waiting for days of
history. Compares strategy equity against what pure buy&hold of each ETF
would have done over the same period.

Read-only: never places orders.

Usage:
    python -m trader.app.run_performance
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

TRACK_PATH = "beta_kis_track.jsonl"


def load_track(path: str = TRACK_PATH) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def inception(track: list[dict]) -> dict | None:
    """First record with a trustworthy equity (clean era has equity_krw)."""
    for r in track:
        if r.get("equity_krw"):
            return r
    return None


def pct(a: float, b: float) -> float:
    return a / b - 1.0 if b else 0.0


def benchmark_return(yf_symbol: str, since_iso: str) -> float | None:
    """Buy&hold return of one ETF from `since` to the latest close (yfinance)."""
    try:
        from trader.data.research_provider import _yf_download_normalize
        rows = _yf_download_normalize(yf_symbol, years=1, auto_adjust=False)
    except Exception:
        return None
    since = datetime.fromisoformat(since_iso).date()
    base = None
    for r in rows:
        if r["ts"].date() >= since and base is None:
            base = r["close"]
    if not base or not rows:
        return None
    return pct(rows[-1]["close"], base)


def main() -> None:
    from trader.app.run_daily import build_kis_client, _load_dotenv
    if "KIS_APP_KEY" not in os.environ:
        _load_dotenv()
    kis = build_kis_client()

    snap = kis.account_snapshot()
    fx = kis.usd_krw_rate(default=-1.0)
    fx_note = "" if fx > 0 else " (FX unavailable — USD legs skipped)"
    usd_fx = fx if fx > 0 else 0.0

    ovr_val = sum(q * snap["marks"].get((m, t), 0.0) * usd_fx
                  for (m, t), q in snap["positions"].items() if m == "NASDAQ")
    dom_val = sum(q * snap["marks"].get((m, t), 0.0)
                  for (m, t), q in snap["positions"].items() if m == "KOSPI")
    equity = snap["nass_krw"] - snap["ovr_purchase_krw"] + ovr_val

    track = load_track()
    base = inception(track)
    now = datetime.now(tz=timezone.utc)

    print("=" * 64)
    print(f"[PAPER PERFORMANCE] {now:%Y-%m-%d %H:%M} UTC{fx_note}")
    print("=" * 64)
    print(f"  equity        : {equity:,.0f} KRW")
    print(f"  cash          : {snap['cash_krw']:,.0f} KRW")
    for (m, t), q in sorted(snap["positions"].items()):
        mark = snap["marks"].get((m, t), 0.0)
        val = q * mark * (usd_fx if m == "NASDAQ" else 1.0)
        w = val / equity if equity else 0.0
        print(f"  {t:>7} [{m}] : {q} sh @ {mark:,.2f} → {val:,.0f} KRW ({w:.1%})")

    if base:
        since = base["as_of"][:10]
        ret = pct(equity, base["equity_krw"])
        print(f"\n  since {since} (clean-era inception, {base['equity_krw']:,.0f} KRW):")
        print(f"  strategy      : {ret:+.2%}")
        for label, sym in (("SPY b&h", "SPY"), ("KODEX b&h", "069500.KS")):
            br = benchmark_return(sym, base["as_of"])
            if br is not None:
                print(f"  {label:<13} : {br:+.2%}")
        print("\n  (Honest note: this is risk-managed BETA — expect market-like")
        print("   returns with smaller drawdowns, not outperformance.)")

    subs = [r for r in track if r.get("submitted_odno")]
    if subs:
        print(f"\n  fills submitted (clean era): {len(subs)}")
        for r in subs[-5:]:
            print(f"    {r['as_of'][:16]} {r['market']} {r['side']} {r['qty']} {r['etf']}"
                  f" (ODNO {r['submitted_odno']})")


if __name__ == "__main__":
    main()
