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
"""
from __future__ import annotations

import csv
import io
import logging
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
    """
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
            with httpx.Client(timeout=20) as c:
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
        return tickers

    except Exception as exc:
        logger.warning(
            "load_sp500: failed to fetch from GitHub (%s); using fallback list.", exc
        )
        return list(_SP500_FALLBACK)


# ---------------------------------------------------------------------------
# Combined universe
# ---------------------------------------------------------------------------

def universe(us_limit: int = 120, kr: bool = True) -> list[tuple[str, str]]:
    """Build the combined research universe.

    Returns a list of (ticker, market) tuples:
      - Up to *us_limit* S&P 500 symbols tagged as "NASDAQ" (for the
        cost/currency model — acceptable for research).
      - All KOSPI_LARGECAP symbols tagged as "KOSPI" (if kr=True).

    SURVIVORSHIP BIAS WARNING: both lists reflect current membership only.

    Args:
        us_limit: Maximum number of S&P 500 symbols to include (default 120).
        kr:       Include KOSPI large-caps (default True).
    """
    sp500 = load_sp500()
    result: list[tuple[str, str]] = [
        (ticker, "NASDAQ") for ticker in sp500[:us_limit]
    ]
    if kr:
        result.extend((ticker, "KOSPI") for ticker in KOSPI_LARGECAP)
    return result
