# trader/app/fetch_edgar_fundamentals.py
"""RESEARCH ONLY — download point-in-time fundamentals from SEC EDGAR.

For each US (NASDAQ-tagged) universe ticker, fetch and store the point-in-time
series for net income (quarterly), stockholders' equity, and shares outstanding.
Resumable (skips tickers already saved). SEC-throttled.

Output: fundamentals_edgar/{TICKER}.json with ISO-date series. NEVER used in the
live/parity path.

Usage:
    python -m trader.app.fetch_edgar_fundamentals [--limit N]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time

import httpx

from trader.data import edgar

OUT_DIR = "fundamentals_edgar"


def _us_tickers(data_dir: str = "research_data") -> list[str]:
    out = []
    for p in sorted(glob.glob(os.path.join(data_dir, "NASDAQ_*.parquet"))):
        base = os.path.basename(p)
        out.append(base[len("NASDAQ_"):-len(".parquet")])
    return out


def _ser_to_json(series: list[dict]) -> list[dict]:
    return [{"period_end": r["period_end"].isoformat(),
             "filed": r["filed"].isoformat(), "val": r["val"]} for r in series]


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="[RESEARCH ONLY] EDGAR fundamentals fetch")
    p.add_argument("--limit", type=int, default=0, help="max tickers (0 = all)")
    p.add_argument("--data-dir", default="research_data")
    args = p.parse_args(argv)

    os.makedirs(OUT_DIR, exist_ok=True)
    tickers = _us_tickers(args.data_dir)
    if args.limit:
        tickers = tickers[:args.limit]

    client = httpx.Client(timeout=30)
    print(f"[EDGAR] resolving CIK map …")
    cik_map = edgar.ticker_to_cik(client)
    print(f"[EDGAR] {len(cik_map)} tickers in SEC map; universe={len(tickers)}")

    fetched = skipped = missing = 0
    for i, tk in enumerate(tickers):
        out_path = os.path.join(OUT_DIR, f"{tk}.json")
        if os.path.exists(out_path):
            skipped += 1
            continue
        cik = cik_map.get(tk)
        if not cik:
            missing += 1
            continue
        try:
            ni = edgar.quarterly_series(edgar.fetch_concept(client, cik, "NetIncomeLoss"))
            time.sleep(0.15)
            eq = edgar.instant_series(edgar.first_available_concept(client, cik, edgar.EQUITY_CONCEPTS))
            time.sleep(0.15)
            sh = edgar.instant_series(edgar.first_available_concept(client, cik, edgar.SHARES_CONCEPTS))
            time.sleep(0.15)
        except Exception as exc:
            print(f"  ERR {tk}: {str(exc)[:80]}")
            missing += 1
            continue
        if not ni or not eq:
            missing += 1
            continue
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump({"ticker": tk, "cik": cik,
                       "ni_quarterly": _ser_to_json(ni),
                       "equity": _ser_to_json(eq),
                       "shares": _ser_to_json(sh)}, fh)
        fetched += 1
        if (i + 1) % 25 == 0:
            print(f"  … {i+1}/{len(tickers)} (fetched={fetched} skipped={skipped} missing={missing})")

    print(f"[EDGAR] done. fetched={fetched} skipped={skipped} missing={missing} "
          f"→ {OUT_DIR}/")


if __name__ == "__main__":
    main()
