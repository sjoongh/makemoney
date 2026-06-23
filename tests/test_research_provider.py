# tests/test_research_provider.py
"""Tests for ResearchDataProvider — RESEARCH ONLY, no live network.

Sources by market:
    NASDAQ  →  yfinance library  (network call isolated behind an injectable
               ``us_downloader`` — tests pass a fake, never hit the network)
    KOSPI   →  Naver Finance XML (via httpx.MockTransport)
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone

import httpx
import pytest

from trader.core.events import Market
from trader.data.research_provider import ResearchDataProvider
from trader.data.storage import load_bars

# ---------------------------------------------------------------------------
# US (yfinance) — fake downloader helpers
# ---------------------------------------------------------------------------

# Normalized rows as the real downloader yields them: tz-aware UTC midnight ts.
def _row(date_str: str, o, h, lo, c, v) -> dict:
    ts = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
    return {"ts": ts, "open": float(o), "high": float(h),
            "low": float(lo), "close": float(c), "volume": int(v)}


_US_ROWS = [
    _row("20230103", 130, 133, 129, 131, 100_000),
    _row("20230104", 127, 131, 126, 129, 110_000),
    _row("20230105", 128, 132, 127, 130, 105_000),
]


def _fake_us_downloader(
    rows: list[dict] | None = None,
    *,
    raise_exc: Exception | None = None,
    counter: list[int] | None = None,
    capture: dict | None = None,
):
    """Build a fake us_downloader callable matching the real signature."""
    rows = _US_ROWS if rows is None else rows

    def _dl(ticker: str, *, years: int, auto_adjust: bool) -> list[dict]:
        if counter is not None:
            counter[0] += 1
        if capture is not None:
            capture.update(ticker=ticker, years=years, auto_adjust=auto_adjust)
        if raise_exc is not None:
            raise raise_exc
        # Return fresh copies so callers can't mutate shared state
        return [dict(r) for r in rows]

    return _dl


def _us_provider(downloader, cache_dir: str) -> ResearchDataProvider:
    return ResearchDataProvider(us_downloader=downloader, cache_dir=cache_dir)


# ---------------------------------------------------------------------------
# Naver XML payload helpers
# ---------------------------------------------------------------------------

# Naver XML format: data="YYYYMMDD|open|high|low|close|volume"
_NAVER_ROWS = [
    ("20230103", 130, 133, 129, 131, 100_000),
    ("20230104", 127, 131, 126, 129, 110_000),
    ("20230105", 128, 132, 127, 130, 105_000),
]


def _make_naver_xml(rows: list[tuple] | None = None) -> str:
    rows = rows or _NAVER_ROWS
    items = "\n".join(
        f'<item data="{r[0]}|{r[1]}|{r[2]}|{r[3]}|{r[4]}|{r[5]}" />'
        for r in rows
    )
    return f"""<?xml version="1.0" encoding="EUC-KR" ?>
<protocol>
<chartdata symbol="005930" name="삼성전자" count="{len(rows)}" timeframe="day">
{items}
</chartdata>
</protocol>"""


def _naver_transport(xml: str | None = None, status_code: int = 200) -> httpx.MockTransport:
    body = (xml or _make_naver_xml()).encode("utf-8")

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=body)

    return httpx.MockTransport(_handler)


def _naver_provider(transport: httpx.MockTransport, cache_dir: str) -> ResearchDataProvider:
    client = httpx.Client(transport=transport)
    return ResearchDataProvider(client=client, cache_dir=cache_dir)


# ---------------------------------------------------------------------------
# 1. US (yfinance) — bar building from normalized rows
# ---------------------------------------------------------------------------

class TestUSDailyHistory:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_returns_ascending_bar_events(self):
        # rows deliberately out of order — provider must sort ascending
        shuffled = [_US_ROWS[2], _US_ROWS[0], _US_ROWS[1]]
        p = _us_provider(_fake_us_downloader(shuffled), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)

        assert len(bars) == 3
        tss = [b.ts for b in bars]
        assert tss == sorted(tss)

    def test_ohlcv_values_preserved(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)

        b = bars[0]  # 20230103: 130/133/129/131/100000
        assert b.open == 130.0
        assert b.high == 133.0
        assert b.low == 129.0
        assert b.close == 131.0
        assert b.volume == 100_000

    def test_volume_preserved(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)
        assert [b.volume for b in bars] == [100_000, 110_000, 105_000]

    def test_timestamps_are_tz_aware(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)
        for b in bars:
            assert b.ts.tzinfo is not None

    def test_symbol_market_and_currency_nasdaq(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)
        for b in bars:
            assert b.symbol.ticker == "AAPL"
            assert b.symbol.market == Market.NASDAQ
            assert b.symbol.currency == "USD"

    def test_use_adjusted_forwarded_as_auto_adjust(self):
        cap: dict = {}
        p = _us_provider(_fake_us_downloader(capture=cap), self.tmp)
        p.daily_history("AAPL", "NASDAQ", use_adjusted=True, refresh=True)
        assert cap["auto_adjust"] is True

        cap2: dict = {}
        p2 = _us_provider(_fake_us_downloader(capture=cap2), tempfile.mkdtemp())
        p2.daily_history("AAPL", "NASDAQ", use_adjusted=False, refresh=True)
        assert cap2["auto_adjust"] is False

    def test_years_forwarded_to_downloader(self):
        cap: dict = {}
        p = _us_provider(_fake_us_downloader(capture=cap), self.tmp)
        p.daily_history("AAPL", "NASDAQ", years=7, refresh=True)
        assert cap["years"] == 7


# ---------------------------------------------------------------------------
# 2. US error handling — downloader failures propagate as RuntimeError
# ---------------------------------------------------------------------------

class TestUSErrorHandling:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_downloader_runtime_error_propagates(self):
        dl = _fake_us_downloader(raise_exc=RuntimeError("empty result"))
        p = _us_provider(dl, self.tmp)
        with pytest.raises(RuntimeError, match="empty result"):
            p.daily_history("BADTICK", "NASDAQ", refresh=True)

    def test_rate_limit_message_propagates(self):
        dl = _fake_us_downloader(raise_exc=RuntimeError("429 rate-limit"))
        p = _us_provider(dl, self.tmp)
        with pytest.raises(RuntimeError, match="429"):
            p.daily_history("AAPL", "NASDAQ", refresh=True)


# ---------------------------------------------------------------------------
# 3. Default downloader — real-row normalization (no network)
# ---------------------------------------------------------------------------

class TestDefaultUSDownloaderNormalization:
    """Exercise _default_research_us_downloader's DataFrame→rows logic with a
    fake yfinance module injected into sys.modules (still no network)."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def _install_fake_yfinance(self, df_or_seq):
        """Install a fake yfinance. Pass a single df, or a list of dfs to
        return one-per-call (for retry tests)."""
        import types

        mod = types.ModuleType("yfinance")
        seq = list(df_or_seq) if isinstance(df_or_seq, list) else [df_or_seq]
        calls = {"i": 0}

        def _download(ticker, **kwargs):
            i = min(calls["i"], len(seq) - 1)
            calls["i"] += 1
            return seq[i]

        mod.download = _download
        mod._calls = calls
        sys.modules["yfinance"] = mod
        return calls

    @staticmethod
    def _no_sleep(*_a, **_k):
        return None

    def teardown_method(self):
        sys.modules.pop("yfinance", None)

    def test_multiindex_columns_flattened(self):
        pd = pytest.importorskip("pandas")
        from trader.data.research_provider import _default_research_us_downloader

        idx = pd.to_datetime(["2023-01-03", "2023-01-04"])
        # MultiIndex (Price, Ticker) like yfinance 1.x for a single symbol
        cols = pd.MultiIndex.from_product(
            [["Open", "High", "Low", "Close", "Volume"], ["AAPL"]],
            names=["Price", "Ticker"],
        )
        data = [
            [130, 133, 129, 131, 100_000],
            [127, 131, 126, 129, 110_000],
        ]
        df = pd.DataFrame(data, index=idx, columns=cols)
        self._install_fake_yfinance(df)

        rows = _default_research_us_downloader(
            "AAPL", years=10, auto_adjust=True, _sleep=self._no_sleep
        )
        assert len(rows) == 2
        assert rows[0]["open"] == 130.0
        assert rows[0]["close"] == 131.0
        assert rows[0]["volume"] == 100_000
        assert rows[0]["ts"].tzinfo is not None

    def test_empty_dataframe_raises(self):
        pd = pytest.importorskip("pandas")
        from trader.data.research_provider import _default_research_us_downloader

        df = pd.DataFrame()
        self._install_fake_yfinance(df)
        with pytest.raises(RuntimeError, match="empty result"):
            _default_research_us_downloader(
                "AAPL", years=10, auto_adjust=True, _sleep=self._no_sleep
            )

    def test_nan_close_rows_skipped(self):
        pd = pytest.importorskip("pandas")
        import numpy as np
        from trader.data.research_provider import _default_research_us_downloader

        idx = pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05"])
        df = pd.DataFrame(
            {
                "Open": [130, np.nan, 128],
                "High": [133, np.nan, 132],
                "Low": [129, np.nan, 127],
                "Close": [131, np.nan, 130],
                "Volume": [100_000, 0, 105_000],
            },
            index=idx,
        )
        self._install_fake_yfinance(df)
        rows = _default_research_us_downloader(
            "AAPL", years=10, auto_adjust=True, _sleep=self._no_sleep
        )
        assert len(rows) == 2  # middle NaN row dropped

    def test_isolated_bad_bars_dropped(self):
        """A few genuinely-inconsistent bars in an otherwise-good series are
        dropped (not fatal); clean bars survive without a retry."""
        pd = pytest.importorskip("pandas")
        from trader.data.research_provider import _default_research_us_downloader

        n = 10
        idx = pd.date_range("2023-01-03", periods=n, freq="D")
        highs = [105.0] * n
        highs[3] = 90.0  # below close → inconsistent
        highs[7] = 90.0
        df = pd.DataFrame(
            {"Open": [100.0] * n, "High": highs, "Low": [99.0] * n,
             "Close": [102.0] * n, "Volume": [1000] * n},
            index=idx,
        )
        calls = self._install_fake_yfinance(df)
        rows = _default_research_us_downloader(
            "AAPL", years=10, auto_adjust=True, _sleep=self._no_sleep
        )
        assert calls["i"] == 1       # no retry — bad bars dropped inline
        assert len(rows) == n - 2    # two bad bars dropped

    def test_systemic_inconsistency_retries_then_succeeds(self):
        """A systemically-corrupt download (most bars bad) raises and retries;
        a clean re-fetch then succeeds."""
        pd = pytest.importorskip("pandas")
        from trader.data.research_provider import _default_research_us_downloader

        n = 8
        idx = pd.date_range("2023-01-03", periods=n, freq="D")
        highs = [90.0] * n   # 6 bad
        highs[0] = highs[1] = 105.0  # 2 good → some kept, triggers systemic-frac raise
        bad = pd.DataFrame(
            {"Open": [100.0] * n, "High": highs, "Low": [99.0] * n,
             "Close": [102.0] * n, "Volume": [1000] * n},
            index=idx,
        )
        good = pd.DataFrame(
            {"Open": [100.0] * n, "High": [105.0] * n, "Low": [99.0] * n,
             "Close": [102.0] * n, "Volume": [1000] * n},
            index=idx,
        )
        calls = self._install_fake_yfinance([bad, good])
        rows = _default_research_us_downloader(
            "AAPL", years=10, auto_adjust=True, _sleep=self._no_sleep
        )
        assert calls["i"] == 2
        assert len(rows) == n

    def test_fp_noise_clamped_no_retry(self):
        """A sub-epsilon high<close (float noise) must be clamped in-place so
        the row is consistent and NO retry happens."""
        pd = pytest.importorskip("pandas")
        from trader.data.research_provider import _default_research_us_downloader

        idx = pd.to_datetime(["2023-01-03"])
        # close one ULP above high — pure float noise (~1e-14)
        c = 27.419137954711914
        h = 27.419137954711910  # < c by ~4e-15
        df = pd.DataFrame(
            {"Open": [27.0], "High": [h], "Low": [26.5], "Close": [c], "Volume": [1000]},
            index=idx,
        )
        calls = self._install_fake_yfinance(df)
        rows = _default_research_us_downloader(
            "MO", years=10, auto_adjust=True, _sleep=self._no_sleep
        )
        assert calls["i"] == 1  # NO retry — clamped on first pass
        assert rows[0]["high"] >= rows[0]["close"]  # repaired

    def test_clamp_helper_leaves_large_inconsistency(self):
        from trader.data.research_provider import _clamp_ohlc_fp_noise

        # genuine garbage: high 120 well below close 131 — must NOT be clamped
        h, lo = _clamp_ohlc_fp_noise(130.0, 120.0, 129.0, 131.0)
        assert h == 120.0  # untouched → caller's consistency check will reject

    def test_persistent_systemic_inconsistency_raises(self):
        pd = pytest.importorskip("pandas")
        from trader.data.research_provider import _default_research_us_downloader

        n = 8
        idx = pd.date_range("2023-01-03", periods=n, freq="D")
        highs = [90.0] * n
        highs[0] = highs[1] = 105.0  # keep 2 good so the systemic-frac check fires
        bad = pd.DataFrame(
            {"Open": [100.0] * n, "High": highs, "Low": [99.0] * n,
             "Close": [102.0] * n, "Volume": [1000] * n},
            index=idx,
        )
        self._install_fake_yfinance(bad)  # always returns bad
        with pytest.raises(RuntimeError, match="inconsisten"):
            _default_research_us_downloader(
                "AAPL", years=10, auto_adjust=True, _max_attempts=2, _sleep=self._no_sleep
            )


# ---------------------------------------------------------------------------
# 4. Parity safety — yfinance must be imported lazily (not at module import)
# ---------------------------------------------------------------------------

def test_importing_research_provider_does_not_import_yfinance():
    """The live/paper import graph must not pull in yfinance.

    Importing trader.data.research_provider must NOT import yfinance — it is
    only imported lazily inside the default US downloader at fetch time.
    """
    # Drop any cached import so the assertion is meaningful.
    sys.modules.pop("yfinance", None)
    import importlib
    import trader.data.research_provider as rp

    importlib.reload(rp)
    assert "yfinance" not in sys.modules


# ---------------------------------------------------------------------------
# 5. Naver (KOSPI) — XML parsing, symbol, currency, URL
# ---------------------------------------------------------------------------

class TestKospiViaYfinance:
    """KOSPI now flows through yfinance (.KS suffix), not Naver."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_kospi_returns_ascending_bar_events(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        bars = p.daily_history("005930", "KOSPI", refresh=True)
        assert len(bars) == 3
        tss = [b.ts for b in bars]
        assert tss == sorted(tss)

    def test_kospi_symbol_and_currency(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        bars = p.daily_history("005930", "KOSPI", refresh=True)
        for b in bars:
            assert b.symbol.ticker == "005930"  # original code, not .KS
            assert b.symbol.market == Market.KOSPI
            assert b.symbol.currency == "KRW"

    def test_kospi_maps_to_ks_suffix_for_yfinance(self):
        cap: dict = {}
        p = _us_provider(_fake_us_downloader(capture=cap), self.tmp)
        p.daily_history("005930", "KOSPI", refresh=True)
        assert cap["ticker"] == "005930.KS"

    def test_kospi_timestamps_are_tz_aware(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        bars = p.daily_history("005930", "KOSPI", refresh=True)
        for b in bars:
            assert b.ts.tzinfo is not None

    def test_kospi_downloader_error_propagates(self):
        dl = _fake_us_downloader(raise_exc=RuntimeError("empty result"))
        p = _us_provider(dl, self.tmp)
        with pytest.raises(RuntimeError, match="empty result"):
            p.daily_history("005930", "KOSPI", refresh=True)


class TestNaverAuditFetch:
    """Naver is audit/fallback only — exercised via _fetch_naver directly,
    NOT via daily_history."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_fetch_naver_parses_xml(self):
        p = _naver_provider(_naver_transport(), self.tmp)
        bars = p._fetch_naver("005930", years=10)
        assert len(bars) == 3
        b = bars[0]  # 20230103|130|133|129|131|100000
        assert b.open == 130.0
        assert b.high == 133.0
        assert b.close == 131.0
        assert b.volume == 100_000
        assert b.symbol.currency == "KRW"
        assert b.symbol.market == Market.KOSPI

    def test_fetch_naver_uses_bare_code_url(self):
        captured: list[str] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(str(request.url))
            return httpx.Response(200, content=_make_naver_xml().encode())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)
        p._fetch_naver("005930", years=10)
        assert len(captured) == 1
        assert "005930" in captured[0]
        assert ".KS" not in captured[0]
        assert "naver" in captured[0]

    def test_fetch_naver_empty_xml_raises(self):
        empty_xml = '<?xml version="1.0"?><protocol><chartdata></chartdata></protocol>'
        p = _naver_provider(_naver_transport(xml=empty_xml), self.tmp)
        with pytest.raises(RuntimeError, match="Malformed|empty"):
            p._fetch_naver("005930", years=10)

    def test_daily_history_does_not_use_naver(self):
        """KOSPI via daily_history must hit the yfinance downloader, never the
        httpx/Naver client."""
        naver_calls = [0]

        def _handler(request: httpx.Request) -> httpx.Response:
            naver_calls[0] += 1
            return httpx.Response(200, content=_make_naver_xml().encode())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        dl_calls = [0]
        p = ResearchDataProvider(
            client=client,
            cache_dir=self.tmp,
            us_downloader=_fake_us_downloader(counter=dl_calls),
        )
        p.daily_history("005930", "KOSPI", refresh=True)
        assert dl_calls[0] == 1   # yfinance path used
        assert naver_calls[0] == 0  # Naver NOT touched


# ---------------------------------------------------------------------------
# 6. Cache — shared behaviour across both markets
# ---------------------------------------------------------------------------

class TestCacheBehaviour:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_second_call_loads_from_cache_not_network_nasdaq(self):
        call_count = [0]
        dl = _fake_us_downloader(counter=call_count)
        p = _us_provider(dl, self.tmp)

        bars1 = p.daily_history("AAPL", "NASDAQ", refresh=True)
        assert call_count[0] == 1

        bars2 = p.daily_history("AAPL", "NASDAQ", refresh=False)
        assert call_count[0] == 1  # no new download

        assert len(bars1) == len(bars2)

    def test_second_call_loads_from_cache_not_network_kospi(self):
        call_count = [0]
        dl = _fake_us_downloader(counter=call_count)
        p = _us_provider(dl, self.tmp)

        bars1 = p.daily_history("005930", "KOSPI", refresh=True)
        assert call_count[0] == 1

        bars2 = p.daily_history("005930", "KOSPI", refresh=False)
        assert call_count[0] == 1  # no new download

        assert len(bars1) == len(bars2)

    def test_cache_file_created_after_first_fetch_nasdaq(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        p.daily_history("AAPL", "NASDAQ", refresh=True)

        cache_path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        assert os.path.exists(cache_path)
        loaded = load_bars(cache_path)
        assert len(loaded) == 3

    def test_cache_file_created_after_first_fetch_kospi(self):
        p = _us_provider(_fake_us_downloader(), self.tmp)
        p.daily_history("005930", "KOSPI", refresh=True)

        cache_path = os.path.join(self.tmp, "KOSPI_005930.parquet")
        assert os.path.exists(cache_path)
        loaded = load_bars(cache_path)
        assert len(loaded) == 3

    def test_refresh_true_bypasses_existing_cache(self):
        call_count = [0]
        dl = _fake_us_downloader(counter=call_count)
        p = _us_provider(dl, self.tmp)

        p.daily_history("AAPL", "NASDAQ", refresh=True)
        p.daily_history("AAPL", "NASDAQ", refresh=True)
        assert call_count[0] == 2
