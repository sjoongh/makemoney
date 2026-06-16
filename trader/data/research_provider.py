# trader/data/research_provider.py
"""RESEARCH ONLY — keyless deep OHLCV history for US and Korean equities.

WARNING: NEVER use this module in live trading, paper trading, or the
backtest/live parity path.  It is strictly for offline research backtests
and strategy evaluation.  Live trading uses KIS (trader/app/fetch_data.py).

No API key required.  Two sources, chosen by market:

  NASDAQ  →  Yahoo Finance chart JSON  (period1/period2 params, ~24 years)
  KOSPI   →  Naver Finance sise XML   (count=2500 bars, ~10 years)

Yahoo: uses period1/period2 URL form which avoids the 429 rate-limit that
the range= param triggers.  Still subject to transient IP throttling if
called too rapidly — cache aggressively (refresh=False on repeat runs).

Naver: XML endpoint, very permissive, returns up to 2500 trading days.

Results are cached as parquet (via trader/data/storage.py) to avoid
repeated network hits.  Cache is keyed {MARKET}_{TICKER}.parquet.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone

import httpx

from trader.core.events import BarEvent, Market, Symbol
from trader.data.storage import load_bars, save_bars

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Browser-like UA — Yahoo and Naver block empty / Python default User-Agent
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Yahoo: period1/period2 form avoids 429 that range= triggers.
# period1 computed from years arg; period2 = far future.
_YAHOO_CHART = (
    "https://query1.finance.yahoo.com/v8/finance/chart/"
    "{sym}?period1={p1}&period2={p2}&interval=1d"
)
_EPOCH_END = 9_999_999_999  # far-future cap for period2

# Naver sise XML — returns up to `count` daily bars ending today, newest last.
_NAVER_SISE = (
    "https://fchart.stock.naver.com/sise.nhn"
    "?symbol={sym}&timeframe=day&count={count}&requestType=0"
)
_NAVER_MAX_BARS = 2500  # Naver API maximum


# ---------------------------------------------------------------------------
# ResearchDataProvider
# ---------------------------------------------------------------------------

class ResearchDataProvider:
    """RESEARCH ONLY — keyless OHLCV history.  NEVER use in live/parity path.

    Sources by market:
        NASDAQ  →  Yahoo Finance JSON  (period1/period2 URL params)
        KOSPI   →  Naver Finance XML  (up to 2500 bars ≈ 10 years)

    Symbol mapping:
        NASDAQ  → ticker as-is       ("AAPL"   → "AAPL")
        KOSPI   → ticker as-is       ("005930" → "005930")  [Naver uses plain KRX code]

    Yahoo symbol mapping (for NASDAQ):
        ticker → ticker              ("AAPL"   → "AAPL")

    (Naver sise endpoint uses the KRX 6-digit code directly, no suffix.)
    """

    # Expose URL templates for introspection / overriding in tests
    YAHOO = _YAHOO_CHART
    NAVER = _NAVER_SISE

    def __init__(
        self,
        client: httpx.Client | None = None,
        cache_dir: str = "research_data",
    ) -> None:
        self._client = client
        self._cache_dir = cache_dir
        self._owns_client = client is None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def daily_history(
        self,
        ticker: str,
        market: str,
        *,
        years: int = 10,
        use_adjusted: bool = True,
        refresh: bool = False,
    ) -> list[BarEvent]:
        """Fetch daily OHLCV bars for *ticker* on *market*.

        Args:
            ticker:       Exchange ticker, e.g. "AAPL" or "005930".
            market:       "NASDAQ" or "KOSPI" (case-insensitive).
            years:        How many years of history to request (default 10).
                          For Yahoo (NASDAQ) this sets period1 relative to now.
                          For Naver (KOSPI) bars are capped at _NAVER_MAX_BARS.
            use_adjusted: Apply split/dividend adjustment to OHLC via adjclose
                          ratio (NASDAQ/Yahoo only — Naver does not provide
                          adjclose, so KOSPI bars are always raw).
            refresh:      If True, always re-fetch from the source even when a
                          cached parquet exists (default False).

        Returns:
            List of BarEvent in ascending timestamp order.

        Raises:
            RuntimeError: On non-200 HTTP, 429 rate-limit, or malformed JSON/XML.
                          Set refresh=False to load from cache instead.
        """
        market_upper = market.upper()
        cache_path = self._cache_path(ticker, market_upper)

        if not refresh and os.path.exists(cache_path):
            return load_bars(cache_path)

        if market_upper == "KOSPI":
            bars = self._fetch_naver(ticker, years=years)
        else:
            bars = self._fetch_yahoo(ticker, market_upper, years=years, use_adjusted=use_adjusted)

        os.makedirs(self._cache_dir, exist_ok=True)
        save_bars(bars, cache_path)
        return bars

    # ------------------------------------------------------------------
    # Internal helpers — cache path
    # ------------------------------------------------------------------

    def _cache_path(self, ticker: str, market: str) -> str:
        return os.path.join(self._cache_dir, f"{market}_{ticker}.parquet")

    # ------------------------------------------------------------------
    # Internal helpers — HTTP client
    # ------------------------------------------------------------------

    def _get(self, url: str, headers: dict) -> httpx.Response:
        """Issue GET using the injected client or a short-lived one."""
        if self._client is not None:
            return self._client.get(url, headers=headers)

        client = httpx.Client(timeout=30)
        try:
            return client.get(url, headers=headers)
        finally:
            client.close()

    # ------------------------------------------------------------------
    # Yahoo Finance — NASDAQ (and other US markets)
    # ------------------------------------------------------------------

    @staticmethod
    def _yahoo_symbol(ticker: str) -> str:
        """NASDAQ tickers pass through as-is to Yahoo."""
        return ticker

    def _fetch_yahoo(
        self,
        ticker: str,
        market: str,
        *,
        years: int,
        use_adjusted: bool,
    ) -> list[BarEvent]:
        sym = self._yahoo_symbol(ticker)
        seconds_per_year = 365.25 * 86400
        p1 = int(time.time() - years * seconds_per_year)
        url = self.YAHOO.format(sym=sym, p1=p1, p2=_EPOCH_END)

        try:
            resp = self._get(url, {"User-Agent": _USER_AGENT})
        except Exception as exc:
            raise RuntimeError(
                f"[RESEARCH] Network error fetching Yahoo data for {sym}: {exc}. "
                "Retry later or set refresh=False to load from cache."
            ) from exc

        if resp.status_code == 429:
            raise RuntimeError(
                f"[RESEARCH] Yahoo rate-limited (429) for {sym}. "
                "Wait a few minutes and retry, or set refresh=False to use cache."
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"[RESEARCH] Yahoo returned HTTP {resp.status_code} for {sym}. "
                "Retry later or set refresh=False to use cache."
            )

        try:
            payload = resp.json()
            result = payload["chart"]["result"]
            if not result:
                raise KeyError("chart.result is empty")
            r0 = result[0]
            timestamps = r0["timestamp"]
            quote = r0["indicators"]["quote"][0]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"[RESEARCH] Malformed Yahoo chart JSON for {sym}: {exc}. "
                "Retry later or set refresh=False to use cache."
            ) from exc

        opens   = quote.get("open",   [])
        highs   = quote.get("high",   [])
        lows    = quote.get("low",    [])
        closes  = quote.get("close",  [])
        volumes = quote.get("volume", [])

        adjcloses: list[float | None] = []
        try:
            adjcloses = r0["indicators"]["adjclose"][0]["adjclose"]
        except (KeyError, IndexError, TypeError):
            adjcloses = [None] * len(timestamps)

        currency = "USD" if market == "NASDAQ" else "KRW"
        symbol = Symbol(ticker, Market(market), currency)

        bars: list[BarEvent] = []
        for i, ts_sec in enumerate(timestamps):
            c = closes[i] if i < len(closes) else None
            if c is None:
                continue

            o   = opens[i]   if i < len(opens)   else None
            h   = highs[i]   if i < len(highs)   else None
            lo  = lows[i]    if i < len(lows)     else None
            v   = volumes[i] if i < len(volumes)  else 0
            adj = adjcloses[i] if i < len(adjcloses) else None

            if o is None or h is None or lo is None:
                continue

            if use_adjusted and adj is not None and c != 0:
                factor = adj / c
                o  = o  * factor
                h  = h  * factor
                lo = lo * factor
                c  = adj  # close = adjclose exactly

            if v is None:
                v = 0

            ts = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
            bars.append(BarEvent(symbol, ts, o, h, lo, c, int(v)))

        bars.sort(key=lambda b: b.ts)
        return bars

    # ------------------------------------------------------------------
    # Naver Finance — KOSPI
    # ------------------------------------------------------------------

    def _fetch_naver(self, ticker: str, *, years: int) -> list[BarEvent]:
        """Fetch KOSPI bars from Naver sise XML endpoint.

        Naver returns up to _NAVER_MAX_BARS (2500) trading days, newest last.
        The *years* arg is used to compute a target bar count (252 trading
        days/year); bars beyond that cutoff are dropped from the oldest end.
        Naver does not provide adjclose — bars are raw (unadjusted).
        """
        # Request the max so we can trim client-side
        url = self.NAVER.format(sym=ticker, count=_NAVER_MAX_BARS)

        try:
            resp = self._get(url, {"User-Agent": _USER_AGENT})
        except Exception as exc:
            raise RuntimeError(
                f"[RESEARCH] Network error fetching Naver data for {ticker}: {exc}. "
                "Retry later or set refresh=False to load from cache."
            ) from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"[RESEARCH] Naver returned HTTP {resp.status_code} for {ticker}. "
                "Retry later or set refresh=False to use cache."
            )

        # Parse XML items: data="YYYYMMDD|open|high|low|close|volume"
        items = re.findall(r'data="([^"]+)"', resp.text)
        if not items:
            raise RuntimeError(
                f"[RESEARCH] Malformed or empty Naver XML for {ticker}. "
                "Retry later or set refresh=False to use cache."
            )

        symbol = Symbol(ticker, Market.KOSPI, "KRW")
        bars: list[BarEvent] = []

        for item in items:
            parts = item.split("|")
            if len(parts) < 6:
                continue
            date_str, o_s, h_s, lo_s, c_s, v_s = parts[:6]
            try:
                o  = float(o_s)
                h  = float(h_s)
                lo = float(lo_s)
                c  = float(c_s)
                v  = int(v_s)
            except (ValueError, TypeError):
                continue
            if c == 0:
                continue

            # Naver date is YYYYMMDD local KST; treat midnight UTC as canonical
            try:
                ts = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            bars.append(BarEvent(symbol, ts, o, h, lo, c, v))

        bars.sort(key=lambda b: b.ts)

        # Trim to requested years from the newest bar backwards
        if bars and years > 0:
            cutoff_secs = bars[-1].ts.timestamp() - years * 365.25 * 86400
            bars = [b for b in bars if b.ts.timestamp() >= cutoff_secs]

        return bars

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "ResearchDataProvider":
        return self

    def __exit__(self, *_: object) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
