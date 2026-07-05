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


def _base_and_latest(yf_symbol: str, since):
    """(base close on/after `since`, latest close) for a yfinance symbol, or None."""
    try:
        from trader.data.research_provider import _yf_download_normalize
        rows = _yf_download_normalize(yf_symbol, years=1, auto_adjust=False)
    except Exception:
        return None
    if not rows:
        return None
    base = next((r["close"] for r in rows if r["ts"].date() >= since), None)
    if not base:
        return None
    return base, rows[-1]["close"]


def inception_usd_fx(track: list[dict]) -> float | None:
    """USD/KRW recorded at (near) clean-era inception — the fx of the earliest
    clean-era US-market track record. Used to express the SPY benchmark in KRW
    without a fragile FX download (yfinance KRW=X trips the OHLC guard)."""
    for r in track:
        if r.get("equity_krw") and r.get("market") == "US" and (r.get("fx") or 0) > 1:
            return r["fx"]
    return None


def benchmark_return(yf_symbol: str, since_iso: str, *, to_krw: bool = False,
                     base_fx: float | None = None, latest_fx: float | None = None) -> float | None:
    """Buy&hold return of one ETF from `since` to the latest close.

    A KRW investor's return on a USD-listed ETF (SPY) is the USD price move
    COMPOUNDED with the KRW/USD change — so for USD names pass to_krw=True plus
    base_fx (USD/KRW at inception) and latest_fx (current USD/KRW); both
    endpoints are converted to KRW, making the row comparable to the KRW-
    denominated strategy return. KRW-native names (069500.KS) pass to_krw=False.
    Returns None (omitted) rather than a misleading USD number if to_krw is
    requested but the FX rates are unavailable."""
    since = datetime.fromisoformat(since_iso).date()
    px = _base_and_latest(yf_symbol, since)
    if px is None:
        return None
    base, latest = px
    if to_krw:
        if not (base_fx and latest_fx and base_fx > 0 and latest_fx > 0):
            return None
        base *= base_fx
        latest *= latest_fx
    return pct(latest, base)


def main() -> None:
    from trader.app.run_daily import build_kis_client, _load_dotenv
    if "KIS_APP_KEY" not in os.environ:
        _load_dotenv()
    kis = build_kis_client()

    snap = kis.account_snapshot()
    fx = kis.usd_krw_rate(default=-1.0)
    usd_fx = fx if fx > 0 else 0.0
    has_us = any(m == "NASDAQ" for (m, _t) in snap["positions"])
    # FX down while holding USD names → equity is genuinely unknown (nass already
    # netted the phantom overseas cost; without ovr_val it would be understated).
    fx_unknown = has_us and usd_fx <= 0
    fx_note = " (FX 조회 실패 — USD 평가 불가)" if fx_unknown else ""

    ovr_val = sum(q * snap["marks"].get((m, t), 0.0) * usd_fx
                  for (m, t), q in snap["positions"].items() if m == "NASDAQ")
    equity = None if fx_unknown else snap["nass_krw"] - snap["ovr_purchase_krw"] + ovr_val

    track = load_track()
    base = inception(track)
    now = datetime.now(tz=timezone.utc)

    print("=" * 64)
    print(f"[PAPER PERFORMANCE] {now:%Y-%m-%d %H:%M} UTC{fx_note}")
    print("=" * 64)
    print(f"  equity        : {'unknown' if equity is None else f'{equity:,.0f} KRW'}")
    print(f"  cash          : {snap['cash_krw']:,.0f} KRW")
    for (m, t), q in sorted(snap["positions"].items()):
        mark = snap["marks"].get((m, t), 0.0)
        val = q * mark * (usd_fx if m == "NASDAQ" else 1.0)
        w = val / equity if equity else 0.0
        print(f"  {t:>7} [{m}] : {q} sh @ {mark:,.2f} → {val:,.0f} KRW ({w:.1%})")

    if base and equity is not None:
        since = base["as_of"][:10]
        ret = pct(equity, base["equity_krw"])
        print(f"\n  since {since} (clean-era inception, {base['equity_krw']:,.0f} KRW):")
        print(f"  strategy      : {ret:+.2%}")
        # SPY is USD-listed → convert to KRW so it's comparable to the KRW strategy
        base_fx = inception_usd_fx(track)
        for label, sym, to_krw in (("SPY b&h (KRW)", "SPY", True), ("KODEX b&h", "069500.KS", False)):
            br = benchmark_return(sym, base["as_of"], to_krw=to_krw,
                                  base_fx=base_fx, latest_fx=usd_fx)
            if br is not None:
                print(f"  {label:<15} : {br:+.2%}")
        print("\n  (Honest note: this is risk-managed BETA — expect market-like")
        print("   returns with smaller drawdowns, not outperformance.)")
    elif base:
        print("\n  strategy return: unavailable (FX down — cannot value USD sleeve)")

    subs = [r for r in track if r.get("submitted_odno")]
    if subs:
        print(f"\n  fills submitted (clean era): {len(subs)}")
        for r in subs[-5:]:
            print(f"    {r['as_of'][:16]} {r['market']} {r['side']} {r['qty']} {r['etf']}"
                  f" (ODNO {r['submitted_odno']})")

    # Refresh the browsable status dashboard as a side effect of this daily
    # reporter (16:45 cron), so status.html stays fresh without its own cron.
    try:
        from trader.app.status_dashboard import gather_status, write_html
        write_html(gather_status(kis=kis, with_benchmarks=True))
        print("\n  → status.html refreshed")
    except Exception as exc:  # noqa: BLE001 — reporting must never crash the run
        print(f"\n  (status.html refresh skipped: {exc})")


if __name__ == "__main__":
    main()
