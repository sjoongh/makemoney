# trader/data/forward_recorder.py
"""RESEARCH ONLY — daily FORWARD data recorder (point-in-time, survivorship-free).

The historical backfill (trader/data/research_provider.py) re-fetches
split/dividend ADJUSTED history from yfinance and overwrites — it is
retroactive and survivorship-biased (current constituents only).

This module records *reality as it prints, each day going forward*:

  1. UNIVERSE MEMBERSHIP LOG (research_data/_universe_log.jsonl):
     one append-only record per day of exactly which symbols were in the
     universe.  This is the key that lets FUTURE backtests use as-of-date
     membership -> no survivorship bias for the forward period.

  2. POINT-IN-TIME RAW BARS (forward_data/{MARKET}_{TICKER}.parquet):
     append-only, UNADJUSTED ("as printed") daily bars.  Never rewritten, so
     no retroactive split/dividend adjustment leaks in.  Stored SEPARATELY
     from the adjusted historical store — never spliced together silently.

Finalized-bar rule (Codex): only bars strictly older than the run date are
appended, so an unfinished/in-progress session is never recorded.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date as _date
from typing import Callable, Optional

from trader.core.events import BarEvent, Market, Symbol
from trader.data.storage import load_bars, save_bars

FORWARD_DIR = "forward_data"
UNIVERSE_LOG_PATH = "research_data/_universe_log.jsonl"

# A fetcher returns recent RAW (unadjusted) daily bars for (ticker, market).
RawFetcher = Callable[[str, str], list[BarEvent]]


def source_symbol(ticker: str, market: str) -> str:
    """yfinance symbol: KOSPI -> '005930.KS', US -> ticker as-is."""
    return f"{ticker}.KS" if market.upper() == "KOSPI" else ticker


def _currency(market: str) -> str:
    return "KRW" if market.upper() == "KOSPI" else "USD"


# ---------------------------------------------------------------------------
# 1. Universe membership log — append-only, idempotent per date
# ---------------------------------------------------------------------------

def append_universe_log(
    symbols: list[tuple[str, str]],
    as_of_date: str,
    *,
    log_path: str = UNIVERSE_LOG_PATH,
    universe_id: str = "default",
    source: str = "yfinance",
) -> bool:
    """Append one membership record for *as_of_date*.

    Idempotent: if *as_of_date* is already logged, does nothing and returns
    False (so re-running the cron same-day is safe).  Returns True on append.
    """
    if _date_already_logged(log_path, as_of_date):
        return False

    record = {
        "as_of_date": as_of_date,
        "universe_id": universe_id,
        "source": source,
        "n": len(symbols),
        "symbols": [
            {
                "ticker": ticker,
                "market": market,
                "currency": _currency(market),
                "source_symbol": source_symbol(ticker, market),
            }
            for ticker, market in symbols
        ],
    }

    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return True


def _date_already_logged(log_path: str, as_of_date: str) -> bool:
    if not os.path.exists(log_path):
        return False
    with open(log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                if json.loads(line).get("as_of_date") == as_of_date:
                    return True
            except json.JSONDecodeError:
                continue
    return False


# ---------------------------------------------------------------------------
# 2. Append-only raw bars — pure merge (finalized-bar rule + dedupe)
# ---------------------------------------------------------------------------

def append_raw_bars(
    existing: list[BarEvent],
    fetched: list[BarEvent],
    today: _date,
) -> list[BarEvent]:
    """Return the merged bar list to persist: existing + newly-finalized bars.

    Rules (pure, no I/O):
      - only bars dated strictly BEFORE *today* are eligible (no unfinished
        session),
      - only dates strictly AFTER the existing max date are appended
        (append-only — history is never rewritten),
      - duplicate dates are dropped (idempotent on retries),
      - result is sorted ascending by timestamp.
    """
    existing_max = max((b.ts.date() for b in existing), default=None)
    seen = {b.ts.date() for b in existing}
    out = list(existing)
    for b in sorted(fetched, key=lambda x: x.ts):
        d = b.ts.date()
        if d >= today:
            continue  # unfinished / in-progress session
        if existing_max is not None and d <= existing_max:
            continue  # append-only: never rewrite history
        if d in seen:
            continue  # dedupe
        out.append(b)
        seen.add(d)
    out.sort(key=lambda b: b.ts)
    return out


# ---------------------------------------------------------------------------
# Default raw fetcher (yfinance, auto_adjust=False) — lazy import (parity guard)
# ---------------------------------------------------------------------------

def _default_raw_fetcher(ticker: str, market: str) -> list[BarEvent]:
    """Fetch ~1y of RAW (unadjusted) daily bars via yfinance and return only
    the recent tail as BarEvents.  auto_adjust=False is REQUIRED — adjusted
    data must never enter the point-in-time forward store."""
    from trader.data.research_provider import _yf_download_normalize

    sym = source_symbol(ticker, market)
    rows = _yf_download_normalize(sym, years=1, auto_adjust=False)
    m = Market(market.upper())
    ccy = _currency(market)
    s = Symbol(ticker, m, ccy)
    return [
        BarEvent(s, r["ts"], r["open"], r["high"], r["low"], r["close"], int(r["volume"]))
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Orchestrator — one daily run
# ---------------------------------------------------------------------------

def record_forward(
    as_of_date: str,
    today: _date,
    universe_list: list[tuple[str, str]],
    *,
    fetch_fn: Optional[RawFetcher] = None,
    forward_dir: str = FORWARD_DIR,
    log_path: str = UNIVERSE_LOG_PATH,
) -> dict:
    """Record one forward day: membership log + append-only raw bars.

    Per-symbol fetch failures are caught and counted (one bad symbol must not
    abort a 700-symbol run).  Returns a summary dict.
    """
    fetch_fn = fetch_fn or _default_raw_fetcher
    os.makedirs(forward_dir, exist_ok=True)

    logged = append_universe_log(universe_list, as_of_date, log_path=log_path)

    appended_bars = 0
    symbols_updated = 0
    errors = 0
    for ticker, market in universe_list:
        path = os.path.join(forward_dir, f"{market.upper()}_{ticker}.parquet")
        existing = load_bars(path) if os.path.exists(path) else []
        try:
            fetched = fetch_fn(ticker, market)
        except Exception:
            errors += 1
            continue
        merged = append_raw_bars(existing, fetched, today)
        gained = len(merged) - len(existing)
        if gained > 0:
            _atomic_save(merged, path)
            appended_bars += gained
            symbols_updated += 1

    return {
        "as_of_date": as_of_date,
        "membership_logged": logged,
        "symbols": len(universe_list),
        "symbols_updated": symbols_updated,
        "bars_appended": appended_bars,
        "errors": errors,
    }


def _atomic_save(bars: list[BarEvent], path: str) -> None:
    """Write to a temp file then rename, so an interrupted run never leaves a
    half-written/corrupt parquet in place of good data."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".parquet.tmp")
    os.close(fd)
    try:
        save_bars(bars, tmp)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
