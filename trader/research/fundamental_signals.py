# trader/research/fundamental_signals.py
"""RESEARCH ONLY — point-in-time fundamental signals for the IC harness.

Joins EDGAR point-in-time fundamentals (filed <= t) with price bars to produce
cross-sectional value signals as ``signal_fn(hist) -> float | None`` closures
compatible with ``signal_eval.evaluate_ic``.

  book_to_market = equity(as_of t) / market_cap
  earnings_yield = ttm_net_income(as_of t) / market_cap
  market_cap     = price(t) * shares_outstanding(as_of t)

CAVEAT (documented honestly): ``price`` here is the research_data ADJUSTED close.
Market cap should use the *unadjusted* price, so for names with splits/large
dividends after t the cross-sectional ranking is distorted. This weakens a
POSITIVE finding (would require a raw-price redo) but barely affects a NULL one.
``filed <= t`` guarantees no look-ahead regardless.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import glob
import json
import os
from datetime import date, datetime
from typing import Callable, Optional

from trader.core.events import BarEvent
from trader.data import edgar

FUND_DIR = "fundamentals_edgar"


def _parse_series(raw: list[dict]) -> list[dict]:
    out = []
    for r in raw:
        try:
            out.append({"period_end": datetime.strptime(r["period_end"], "%Y-%m-%d").date(),
                        "filed": datetime.strptime(r["filed"], "%Y-%m-%d").date(),
                        "val": float(r["val"])})
        except (ValueError, TypeError, KeyError):
            continue
    return out


def load_edgar_fundamentals(fund_dir: str = FUND_DIR) -> dict[str, dict]:
    """Load {ticker -> {ni_quarterly, equity, shares}} with parsed dates."""
    out: dict[str, dict] = {}
    for path in glob.glob(os.path.join(fund_dir, "*.json")):
        if os.path.basename(path).startswith("_"):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                d = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue
        out[d["ticker"]] = {
            "ni_quarterly": _parse_series(d.get("ni_quarterly", [])),
            "equity": _parse_series(d.get("equity", [])),
            "shares": _parse_series(d.get("shares", [])),
        }
    return out


SignalFn = Callable[[list[BarEvent]], Optional[float]]


def make_book_to_market(fund: dict[str, dict]) -> SignalFn:
    def _bm(hist: list[BarEvent]) -> Optional[float]:
        b = hist[-1]
        tk = b.symbol.ticker
        f = fund.get(tk)
        if not f:
            return None
        t = b.ts.date()
        equity = edgar.as_of(f["equity"], t)
        shares = edgar.as_of(f["shares"], t)
        if equity is None or shares is None or shares <= 0 or b.close <= 0:
            return None
        mktcap = b.close * shares
        if mktcap <= 0:
            return None
        return equity / mktcap
    return _bm


def make_earnings_yield(fund: dict[str, dict]) -> SignalFn:
    def _ey(hist: list[BarEvent]) -> Optional[float]:
        b = hist[-1]
        tk = b.symbol.ticker
        f = fund.get(tk)
        if not f:
            return None
        t = b.ts.date()
        ttm_ni = edgar.ttm_as_of(f["ni_quarterly"], t, n=4)
        shares = edgar.as_of(f["shares"], t)
        if ttm_ni is None or shares is None or shares <= 0 or b.close <= 0:
            return None
        mktcap = b.close * shares
        if mktcap <= 0:
            return None
        return ttm_ni / mktcap
    return _ey
