# trader/data/research_provider.py
"""RESEARCH ONLY — keyless deep OHLCV history for US and Korean equities.

WARNING: NEVER use this module in live trading, paper trading, or the
backtest/live parity path.  It is strictly for offline research backtests
and strategy evaluation.  Live trading uses KIS (trader/app/fetch_data.py).

No API key required.  Primary source for BOTH markets is yfinance:

  NASDAQ  →  yfinance  ("AAPL")        full daily history, split/div adjusted
  KOSPI   →  yfinance  ("005930.KS")   full daily history, split/div adjusted

Why yfinance for both: the raw Yahoo chart JSON API now returns HTTP 429 on
*every* call, and Naver's sise XML intermittently serves corrupt OHLC and is
unadjusted.  yfinance (curl_cffi browser impersonation) is clean, adjusted, and
consistent across markets.  The network call is isolated in
``_default_research_us_downloader`` and injectable via the ``us_downloader``
constructor arg so unit tests never hit the network.

Naver (``_fetch_naver``) is retained as an audit/fallback source only — it is
no longer wired into ``daily_history``.  See docs/data-limitations.md.

Results are cached as parquet (via trader/data/storage.py) to avoid
repeated network hits.  Cache is keyed {MARKET}_{TICKER}.parquet.
"""
from __future__ import annotations

import logging
import math
import os
import re
import time
from datetime import datetime, timezone
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

# A bar that is still OHLC-inconsistent after sub-epsilon FP clamping is an
# isolated bad tick — dropped (and logged), not fatal.  But if the share of
# dropped bars exceeds BOTH an absolute floor and a fraction, the series is
# treated as systemically corrupt and the fetch is failed (so it retries /
# errors rather than silently returning a sparse, biased series).
_MAX_DROP_ABS = 5
_MAX_DROP_FRAC = 0.005

from trader.core.events import BarEvent, Market, Symbol
from trader.data.storage import load_bars, save_bars
from trader.data.manifest import (
    DatasetManifest,
    current_git_commit,
    load_manifest,
    save_bars_with_manifest,
    verify,
)
from trader.data.quality import validate_bars

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Browser-like UA — Yahoo and Naver block empty / Python default User-Agent
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Naver sise XML — returns up to `count` daily bars ending today, newest last.
_NAVER_SISE = (
    "https://fchart.stock.naver.com/sise.nhn"
    "?symbol={sym}&timeframe=day&count={count}&requestType=0"
)
_NAVER_MAX_BARS = 2500  # Naver API maximum


# ---------------------------------------------------------------------------
# US downloader — yfinance network boundary (RESEARCH ONLY)
# ---------------------------------------------------------------------------

# A US downloader returns normalized rows, one dict per trading day:
#     {"ts": datetime(tz-aware UTC midnight), "open", "high", "low", "close": float, "volume": int}
# It MUST raise RuntimeError on any failure (empty / malformed / network) so the
# caller's existing error contract (cooldown vs error) keeps working.
USDownloader = Callable[..., list[dict]]


def _clamp_ohlc_fp_noise(
    o: float, h: float, lo: float, c: float, *, rel_tol: float = 1e-6
) -> tuple[float, float]:
    """Repair sub-epsilon OHLC inconsistency from adjusted-price float math.

    yfinance's auto-adjusted O/H/L/C are each multiplied by the same factor and
    rounded independently, so a bar where high == close mathematically can come
    back with high one ULP *below* close (~1e-15).  That is float noise, not
    corruption.  When the high/low is within ``rel_tol`` of the true max/min we
    clamp it; a *larger* discrepancy is left intact so the consistency check
    still rejects genuinely garbage bars.

    Returns the (possibly clamped) (high, low).
    """
    hi = max(o, h, lo, c)
    lwst = min(o, h, lo, c)
    tol = rel_tol * max(abs(o), abs(h), abs(lo), abs(c), 1.0)
    if h < hi and (hi - h) <= tol:
        h = hi
    if lo > lwst and (lo - lwst) <= tol:
        lo = lwst
    return h, lo


def _rows_ohlc_consistent(rows: list[dict]) -> bool:
    """True if every row satisfies high >= max(O,C,L) and low <= min(O,C,H).

    yfinance occasionally returns a transiently-glitched bar under rapid
    bulk fetching (a partial/garbage row that re-fetches clean).  The caller
    uses this to retry rather than poison a never-cached symbol with a
    permanent quality_fail.
    """
    for r in rows:
        o, h, lo, c = r["open"], r["high"], r["low"], r["close"]
        if h < max(o, c, lo) or lo > min(o, c, h) or h < lo:
            return False
    return True


def _default_research_us_downloader(
    ticker: str,
    *,
    years: int,
    auto_adjust: bool,
    _max_attempts: int = 3,
    _sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """RESEARCH ONLY — fetch full US daily history via yfinance, with retry.

    yfinance is imported lazily *inside* this function so the live/paper
    trading path can import trader.data.research_provider without pulling in
    yfinance.  NEVER call this from the backtest/live parity path.

    Retries on either a hard failure (empty/malformed) OR a transient OHLC
    inconsistency (a glitched bar that re-fetches clean), with linear backoff.

    Raises RuntimeError if all attempts fail (missing lib, empty/malformed,
    or persistently inconsistent data).
    """
    last_err: Exception | None = None
    for attempt in range(_max_attempts):
        try:
            rows = _yf_download_normalize(ticker, years=years, auto_adjust=auto_adjust)
            if _rows_ohlc_consistent(rows):
                return rows
            last_err = RuntimeError(
                f"[RESEARCH] Transient OHLC inconsistency for {ticker} "
                f"(attempt {attempt + 1}/{_max_attempts})."
            )
        except RuntimeError as exc:
            last_err = exc
        if attempt < _max_attempts - 1:
            _sleep(1.5 * (attempt + 1))
    assert last_err is not None
    raise last_err


def _yf_download_normalize(
    ticker: str,
    *,
    years: int,
    auto_adjust: bool,
) -> list[dict]:
    """One yfinance download + normalization pass (no retry).  Raises on failure."""
    try:
        import yfinance as yf  # lazy: keep yfinance out of the live import graph
    except ImportError as exc:  # pragma: no cover - env-specific
        raise RuntimeError(
            f"[RESEARCH] yfinance not installed — cannot fetch US history for {ticker}: {exc}"
        ) from exc

    try:
        df = yf.download(
            ticker,
            period=f"{years}y",
            interval="1d",
            auto_adjust=auto_adjust,
            progress=False,
            threads=False,
        )
    except Exception as exc:  # yfinance raises a grab-bag of exceptions
        raise RuntimeError(
            f"[RESEARCH] US history download failed for {ticker}: {exc}"
        ) from exc

    if df is None or len(df) == 0:
        raise RuntimeError(
            f"[RESEARCH] US history download failed for {ticker}: empty result "
            "(bad ticker or transient throttle)."
        )

    # yfinance 1.x returns MultiIndex columns ('Price', 'Ticker') even for a
    # single symbol — flatten to the canonical field level.
    cols_obj = df.columns
    if getattr(cols_obj, "nlevels", 1) > 1:
        df = df.copy()
        df.columns = df.columns.get_level_values(0)

    # Case-insensitive lookup of canonical OHLCV fields.
    lower_map = {str(c).lower(): c for c in df.columns}
    required = ("open", "high", "low", "close", "volume")
    if not all(r in lower_map for r in required):
        raise RuntimeError(
            f"[RESEARCH] US history download failed for {ticker}: "
            f"missing OHLCV columns (got {list(df.columns)})."
        )

    rows: list[dict] = []
    dropped_inconsistent = 0
    for idx, row in df.iterrows():
        c = row[lower_map["close"]]
        if c is None or (isinstance(c, float) and math.isnan(c)):
            continue
        o = row[lower_map["open"]]
        h = row[lower_map["high"]]
        lo = row[lower_map["low"]]
        v = row[lower_map["volume"]]
        if any(x is None or (isinstance(x, float) and math.isnan(x)) for x in (o, h, lo)):
            continue

        # idx is a pandas Timestamp (date for daily bars); canonicalize to UTC midnight.
        ts = datetime(idx.year, idx.month, idx.day, tzinfo=timezone.utc)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            v = 0
        of, hf, lof, cf = float(o), float(h), float(lo), float(c)
        # Repair sub-epsilon high/low float noise from adjusted-price math.
        hf, lof = _clamp_ohlc_fp_noise(of, hf, lof, cf)
        # Drop an isolated bad tick still inconsistent beyond FP tolerance.
        if hf < max(of, cf, lof) or lof > min(of, cf, hf):
            dropped_inconsistent += 1
            logger.warning(
                "DROP_BAD_BAR %s %s — OHLC inconsistent (O=%s H=%s L=%s C=%s)",
                ticker, ts.date(), of, hf, lof, cf,
            )
            continue
        rows.append(
            {
                "ts": ts,
                "open": of,
                "high": hf,
                "low": lof,
                "close": cf,
                "volume": int(v),
            }
        )

    if not rows:
        raise RuntimeError(
            f"[RESEARCH] US history download failed for {ticker}: all rows null/invalid."
        )

    # Reject the symbol if too many bars were inconsistent (systemic corruption).
    considered = len(rows) + dropped_inconsistent
    allowance = max(_MAX_DROP_ABS, _MAX_DROP_FRAC * considered)
    if dropped_inconsistent > allowance:
        raise RuntimeError(
            f"[RESEARCH] {ticker}: systemic OHLC inconsistency — "
            f"{dropped_inconsistent}/{considered} bars dropped (> {allowance:.0f} allowed)."
        )
    if dropped_inconsistent:
        logger.warning(
            "%s: dropped %d/%d inconsistent bar(s) (within tolerance).",
            ticker, dropped_inconsistent, considered,
        )
    return rows


# ---------------------------------------------------------------------------
# ResearchDataProvider
# ---------------------------------------------------------------------------

class ResearchDataProvider:
    """RESEARCH ONLY — keyless OHLCV history.  NEVER use in live/parity path.

    Sources by market (primary = yfinance for both):
        NASDAQ  →  yfinance  ("AAPL")       full daily history, adjusted
        KOSPI   →  yfinance  ("005930.KS")  full daily history, adjusted

    ``_fetch_naver`` remains as an audit/fallback source but is not used by
    ``daily_history``.

    The yfinance network call is isolated behind ``us_downloader`` (defaults to
    ``_default_research_us_downloader``).  Inject a fake in tests to avoid
    real network access.
    """

    # Expose URL template for introspection / overriding in tests
    NAVER = _NAVER_SISE

    def __init__(
        self,
        client: httpx.Client | None = None,
        cache_dir: str = "research_data",
        us_downloader: USDownloader | None = None,
    ) -> None:
        self._client = client
        self._cache_dir = cache_dir
        self._owns_client = client is None
        self._us_downloader: USDownloader = us_downloader or _default_research_us_downloader

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

        manifest_path = cache_path + ".manifest.json"

        if not refresh and os.path.exists(cache_path):
            bars = load_bars(cache_path)
            # If sidecar manifest exists, verify hash matches on load
            if os.path.exists(manifest_path):
                try:
                    m = load_manifest(manifest_path)
                    if not verify(m, bars):
                        import warnings
                        warnings.warn(
                            f"[MANIFEST] Hash mismatch for {cache_path} — "
                            "data changed since manifest was written.",
                            stacklevel=2,
                        )
                except Exception:
                    pass  # best-effort; don't break cache hits
            return bars

        # Both US and KR now go through yfinance (KR via the .KS suffix).  Naver
        # is retained as an audit/fallback source (_fetch_naver) but is no longer
        # the primary KR feed — it intermittently served corrupt OHLC and lacks
        # corporate-action adjustment.  See docs/data-limitations.md.
        bars = self._fetch_yfinance(ticker, market_upper, years=years, use_adjusted=use_adjusted)
        provider_name = "yfinance"
        adjustment = "adjusted" if use_adjusted else "raw"

        os.makedirs(self._cache_dir, exist_ok=True)

        # Quality check for manifest
        quality_passed: bool | None = None
        if bars:
            try:
                report = validate_bars(bars)
                quality_passed = report.passed
            except Exception:
                quality_passed = None

        created_ts = datetime.now(tz=timezone.utc).isoformat()
        dataset_id = f"{market_upper}_{ticker}"

        if bars:
            save_bars_with_manifest(
                bars,
                cache_path,
                provider=provider_name,
                adjustment=adjustment,
                created_ts=created_ts,
                dataset_id=dataset_id,
                code_commit=current_git_commit(),
                quality_passed=quality_passed,
            )
        else:
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
    # Equities — yfinance (US + KR via .KS suffix)
    # ------------------------------------------------------------------

    @staticmethod
    def _yf_symbol(ticker: str, market: str) -> str:
        """Map an exchange ticker to the yfinance symbol.

        KOSPI  →  "{code}.KS"  ("005930" → "005930.KS")
        US     →  ticker as-is ("AAPL"   → "AAPL")
        """
        if market == "KOSPI":
            return f"{ticker}.KS"
        return ticker

    def _fetch_yfinance(
        self,
        ticker: str,
        market: str,
        *,
        years: int,
        use_adjusted: bool,
    ) -> list[BarEvent]:
        """Fetch daily history via the injected ``us_downloader`` (yfinance).

        Handles both US and KR (KOSPI via the .KS suffix).  The downloader
        returns normalized rows and raises RuntimeError on any failure
        (empty / malformed / network), which propagates unchanged.
        """
        yf_sym = self._yf_symbol(ticker, market)
        rows = self._us_downloader(yf_sym, years=years, auto_adjust=use_adjusted)

        currency = "KRW" if market == "KOSPI" else "USD"
        # Keep the original exchange ticker on the Symbol (not the .KS form).
        symbol = Symbol(ticker, Market(market), currency)

        bars: list[BarEvent] = []
        for r in rows:
            ts = r["ts"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            bars.append(
                BarEvent(
                    symbol,
                    ts,
                    float(r["open"]),
                    float(r["high"]),
                    float(r["low"]),
                    float(r["close"]),
                    int(r["volume"]),
                )
            )

        bars.sort(key=lambda b: b.ts)
        return bars

    # ------------------------------------------------------------------
    # Naver Finance — KOSPI
    # ------------------------------------------------------------------

    def _fetch_naver(self, ticker: str, *, years: int) -> list[BarEvent]:
        """AUDIT/FALLBACK ONLY — fetch KOSPI bars from Naver sise XML endpoint.

        No longer wired into ``daily_history`` (KOSPI now uses yfinance .KS).
        Kept for cross-checking / fallback: Naver is raw (unadjusted) and has
        intermittently served corrupt OHLC, so it is not the primary KR feed.

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
