# trader/data/universe.py
"""RESEARCH ONLY — Universe builder for historical-data accumulator.

Provides a broad US (S&P 500) + KR (KOSPI large-cap) universe for the
offline data accumulator.  NEVER use in live/paper trading or the
backtest/live parity path.

SURVIVORSHIP BIAS WARNING:
  S&P 500 constituents are fetched live from the datasets/s-and-p-500-companies
  GitHub CSV — this reflects TODAY's index membership.  Symbols that were
  removed (delisted, merged, reclassified) are absent.  KOSPI_LARGECAP is a
  hardcoded snapshot of current large-caps.  Both lists are survivorship-biased
  and unsuitable for point-in-time research without further correction.

  See docs/data-limitations.md for a full account of all data limitations.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KOSPI large-caps — hardcoded ~30 symbols (6-digit KRX codes).
# CURRENT large-caps = survivorship-biased; see module docstring.
# ---------------------------------------------------------------------------

KOSPI_LARGECAP: list[str] = [
    "005930",  # Samsung Electronics
    "000660",  # SK Hynix
    "005380",  # Hyundai Motor
    "035420",  # NAVER
    "051910",  # LG Chem
    "005490",  # POSCO Holdings
    "035720",  # Kakao
    "012330",  # Hyundai Mobis
    "028260",  # Samsung C&T
    "105560",  # KB Financial
    "055550",  # Shinhan Financial
    "066570",  # LG Electronics
    "003670",  # POSCO Future M
    "096770",  # SK Innovation
    "015760",  # KEPCO
    "017670",  # SK Telecom
    "034730",  # SK Inc.
    "003550",  # LG Corp
    "009150",  # Samsung Electro-Mechanics
    "011200",  # HMM
    "086790",  # Hana Financial
    "010130",  # Korea Zinc
    "032830",  # Samsung Life Insurance
    "018260",  # Samsung SDS
    "010950",  # S-Oil
    "024110",  # Industrial Bank of Korea
    "030200",  # KT Corp
    "161390",  # Hanwha Solutions
    "251270",  # Netmarble
    "036570",  # NCsoft
]

# ---------------------------------------------------------------------------
# S&P 500 — fetched from GitHub datasets repo
# ---------------------------------------------------------------------------

_SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies"
    "/main/data/constituents.csv"
)

# Fallback list if network fetch fails (a small sample of well-known names)
_SP500_FALLBACK: list[str] = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "BRK-B", "LLY",
    "TSLA", "V", "UNH", "XOM", "JPM", "JNJ", "PG", "MA", "HD", "AVGO",
    "MRK", "CVX",
]


def load_sp500(client: httpx.Client | None = None) -> list[str]:
    """Fetch current S&P 500 constituent tickers via the GitHub CSV dataset.

    Returns:
        List of ticker strings with Yahoo Finance normalisation applied
        (dots replaced by dashes, e.g. BRK.B → BRK-B).

    Falls back to a small hardcoded list if the network request fails.

    Args:
        client: Optional injectable httpx.Client (used in tests to avoid
                real network calls).  If None, a short-lived client is used.

    Real runs (client is None): a FRESH cache (< _CACHE_MAX_AGE_DAYS old) is
    preferred and the flaky GitHub raw endpoint is skipped entirely — it can
    HANG and block the daily accumulator, and the constituent list changes
    rarely. When the cache file is older than that, a refresh-fetch is
    attempted (tight timeout) and on failure the stale cache is still used
    (never the tiny fallback while a cache exists). Delete the cache file to
    force a refresh on the next run. Tests inject a client to exercise the
    fetch/parse/fallback paths.
    """
    if client is None:
        cached = _load_sp500_cache()
        if cached and _cache_age_days() <= _CACHE_MAX_AGE_DAYS:
            return cached
        # stale or missing cache → fall through to a (tight-timeout) fetch;
        # the except-path below prefers the stale cache over the fallback.

    _headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        if client is not None:
            resp = client.get(_SP500_CSV_URL, headers=_headers)
        else:
            # Tight timeout: the GitHub raw endpoint can HANG. Since a committed
            # cache is the fallback, fail fast (don't block the accumulator) and
            # use the cache. connect+read capped so a stalled socket resolves
            # in seconds, not tens of seconds.
            with httpx.Client(
                timeout=httpx.Timeout(6.0, connect=4.0)
            ) as c:
                resp = c.get(_SP500_CSV_URL, headers=_headers)

        resp.raise_for_status()
        text = resp.text

        reader = csv.DictReader(io.StringIO(text))
        tickers: list[str] = []
        for row in reader:
            # Column name varies between "Symbol" and "symbol"
            raw = row.get("Symbol") or row.get("symbol") or ""
            raw = raw.strip()
            if raw:
                # Yahoo Finance normalisation: "." → "-" (e.g. BRK.B → BRK-B)
                tickers.append(raw.replace(".", "-"))
        if not tickers:
            raise ValueError("CSV parsed but contained no tickers")
        _save_sp500_cache(tickers)   # refresh disk cache on a good full fetch
        return tickers

    except Exception as exc:
        # A transient fetch failure must NOT collapse the universe to the tiny
        # hardcoded fallback (that silently shrank the accumulator to ~20 US
        # names). Prefer the last good disk cache; only then the fallback.
        cached = _load_sp500_cache()
        if cached:
            logger.warning(
                "load_sp500: fetch failed (%s); using cached list (%d tickers).",
                exc, len(cached),
            )
            return cached
        logger.warning(
            "load_sp500: fetch failed (%s) and no cache; using small fallback list.", exc
        )
        return list(_SP500_FALLBACK)


_SP500_CACHE_PATH = "research_data/_sp500_cache.json"
_CACHE_MAX_AGE_DAYS = 30.0


def _cache_age_days(path: str = _SP500_CACHE_PATH) -> float:
    """Age of the cache file in days; +inf when missing/unreadable."""
    import time
    try:
        return (time.time() - os.path.getmtime(path)) / 86400.0
    except OSError:
        return float("inf")


def _save_sp500_cache(tickers: list[str], path: str = _SP500_CACHE_PATH) -> None:
    # Only cache a plausibly-full list, so small injected test samples don't
    # overwrite the real cache.
    if len(tickers) < 400:
        return
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(tickers, fh)
    except OSError:
        pass  # cache is best-effort


def _load_sp500_cache(path: str = _SP500_CACHE_PATH) -> list[str]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list) and len(data) >= 400:
            return [str(t) for t in data]
    except (OSError, json.JSONDecodeError):
        pass
    return []


# ---------------------------------------------------------------------------
# Combined universe
# ---------------------------------------------------------------------------

def universe(
    us_limit: int = 503, kr: bool = True, kr_limit: int = 200
) -> list[tuple[str, str]]:
    """Build the combined research universe.

    Returns a list of (ticker, market) tuples:
      - Up to *us_limit* S&P 500 symbols tagged as "NASDAQ" (for the
        cost/currency model — acceptable for research).
      - Up to *kr_limit* top-marketcap KOSPI common stocks tagged "KOSPI"
        (if kr=True).  Sourced from the baked KOSPI_TOP200 snapshot; falls
        back to the small KOSPI_LARGECAP list if that import is unavailable.

    SURVIVORSHIP BIAS WARNING: both lists reflect current membership only.
    Delisted and historically-removed names are excluded — results derived
    from this universe will be inflated.  See docs/data-limitations.md.

    Args:
        us_limit: Maximum number of S&P 500 symbols to include (default 503 = all).
        kr:       Include KOSPI names (default True).
        kr_limit: Maximum number of KOSPI names to include (default 200).
    """
    logger.warning(
        "universe() called — SURVIVORSHIP-BIASED: current constituents only; "
        "excludes delisted/removed names; see docs/data-limitations.md"
    )
    sp500 = load_sp500()
    result: list[tuple[str, str]] = [
        (ticker, "NASDAQ") for ticker in sp500[:us_limit]
    ]
    if kr:
        try:
            from trader.data.kospi_universe import KOSPI_TOP200 as _kr_list
        except Exception:  # pragma: no cover - fallback if snapshot missing
            _kr_list = KOSPI_LARGECAP
        result.extend((ticker, "KOSPI") for ticker in _kr_list[:kr_limit])
    return result
