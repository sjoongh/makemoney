# tests/test_research_provider.py
"""Tests for ResearchDataProvider — RESEARCH ONLY, no live network.

All tests use httpx.MockTransport so no real Yahoo/Naver requests are made.

Sources by market:
    NASDAQ  →  Yahoo Finance JSON  (period1/period2 params)
    KOSPI   →  Naver Finance XML  (sise endpoint)
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

import httpx
import pytest

from trader.core.events import Market
from trader.data.research_provider import ResearchDataProvider
from trader.data.storage import load_bars

# ---------------------------------------------------------------------------
# Yahoo payload helpers
# ---------------------------------------------------------------------------

_TS = [1672704000, 1672790400, 1672876800]  # 2023-01-03, 04, 05 UTC

_OPENS    = [130.0, 127.0, 128.0]
_HIGHS    = [133.0, 131.0, 132.0]
_LOWS     = [129.0, 126.0, 127.0]
_CLOSES   = [131.0, 129.0, 130.0]
_VOLUMES  = [100_000, 110_000, 105_000]
_ADJCLOSES = [130.0, 128.0, 129.0]  # different from close → forces adj math


def _make_yahoo_payload(
    timestamps: list[int] | None = None,
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    closes: list[float] | None = None,
    volumes: list[int] | None = None,
    adjcloses: list[float] | None = None,
    include_adjclose: bool = True,
) -> dict:
    timestamps = timestamps or _TS
    opens      = opens      or _OPENS
    highs      = highs      or _HIGHS
    lows       = lows       or _LOWS
    closes     = closes     or _CLOSES
    volumes    = volumes    or _VOLUMES
    adjcloses  = adjcloses  or _ADJCLOSES

    indicators: dict = {
        "quote": [{"open": opens, "high": highs, "low": lows,
                   "close": closes, "volume": volumes}]
    }
    if include_adjclose:
        indicators["adjclose"] = [{"adjclose": adjcloses}]

    return {
        "chart": {
            "result": [{"timestamp": timestamps, "indicators": indicators}],
            "error": None,
        }
    }


def _yahoo_transport(payload: dict, status_code: int = 200) -> httpx.MockTransport:
    body = json.dumps(payload).encode()

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=body)

    return httpx.MockTransport(_handler)


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


# ---------------------------------------------------------------------------
# Helper: build provider with a given transport
# ---------------------------------------------------------------------------

def _provider(transport: httpx.MockTransport, cache_dir: str) -> ResearchDataProvider:
    client = httpx.Client(transport=transport)
    return ResearchDataProvider(client=client, cache_dir=cache_dir)


# ---------------------------------------------------------------------------
# 1. Yahoo (NASDAQ) — basic bar parsing and adjusted OHLC math
# ---------------------------------------------------------------------------

class TestYahooDailyHistory:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_returns_ascending_bar_events(self):
        p = _provider(_yahoo_transport(_make_yahoo_payload()), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)

        assert len(bars) == 3
        tss = [b.ts for b in bars]
        assert tss == sorted(tss)

    def test_adjusted_ohlc_math(self):
        p = _provider(_yahoo_transport(_make_yahoo_payload()), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", use_adjusted=True, refresh=True)

        b = bars[0]
        factor = _ADJCLOSES[0] / _CLOSES[0]
        assert abs(b.open  - _OPENS[0]  * factor) < 1e-9
        assert abs(b.high  - _HIGHS[0]  * factor) < 1e-9
        assert abs(b.low   - _LOWS[0]   * factor) < 1e-9
        assert abs(b.close - _ADJCLOSES[0])        < 1e-9  # close = adjclose exactly

    def test_timestamps_are_tz_aware(self):
        p = _provider(_yahoo_transport(_make_yahoo_payload()), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)
        for b in bars:
            assert b.ts.tzinfo is not None

    def test_symbol_market_and_currency_nasdaq(self):
        p = _provider(_yahoo_transport(_make_yahoo_payload()), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)
        for b in bars:
            assert b.symbol.ticker == "AAPL"
            assert b.symbol.market == Market.NASDAQ
            assert b.symbol.currency == "USD"

    def test_volume_preserved(self):
        p = _provider(_yahoo_transport(_make_yahoo_payload()), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)
        assert [b.volume for b in bars] == _VOLUMES

    def test_null_close_rows_skipped(self):
        payload = _make_yahoo_payload(
            closes=[131.0, None, 130.0],
            adjcloses=[130.0, None, 129.0],
        )
        p = _provider(_yahoo_transport(payload), self.tmp)
        bars = p.daily_history("AAPL", "NASDAQ", refresh=True)
        assert len(bars) == 2

    def test_yahoo_url_contains_period_params(self):
        """URL must use period1/period2 form, not range=."""
        captured: list[str] = []
        payload = _make_yahoo_payload()

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(str(request.url))
            return httpx.Response(200, content=json.dumps(payload).encode())

        transport = httpx.MockTransport(_handler)
        client = httpx.Client(transport=transport)
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)
        p.daily_history("AAPL", "NASDAQ", refresh=True)

        assert len(captured) == 1
        assert "period1=" in captured[0]
        assert "period2=" in captured[0]
        assert "range=" not in captured[0]


# ---------------------------------------------------------------------------
# 2. Yahoo error handling
# ---------------------------------------------------------------------------

class TestYahooErrorHandling:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_non_200_raises_runtime_error(self):
        p = _provider(_yahoo_transport({}, status_code=500), self.tmp)
        with pytest.raises(RuntimeError, match="500"):
            p.daily_history("AAPL", "NASDAQ", refresh=True)

    def test_429_raises_runtime_error_with_rate_limit_message(self):
        p = _provider(_yahoo_transport({}, status_code=429), self.tmp)
        with pytest.raises(RuntimeError, match="429"):
            p.daily_history("AAPL", "NASDAQ", refresh=True)

    def test_malformed_json_raises_runtime_error(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b'{"chart": {"result": null}}')

        transport = httpx.MockTransport(_handler)
        client = httpx.Client(transport=transport)
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)
        with pytest.raises(RuntimeError, match=r"Malformed"):
            p.daily_history("AAPL", "NASDAQ", refresh=True)


# ---------------------------------------------------------------------------
# 3. Naver (KOSPI) — XML parsing, symbol, currency, URL
# ---------------------------------------------------------------------------

class TestNaverKospi:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_kospi_returns_ascending_bar_events(self):
        p = _provider(_naver_transport(), self.tmp)
        bars = p.daily_history("005930", "KOSPI", refresh=True)

        assert len(bars) == 3
        tss = [b.ts for b in bars]
        assert tss == sorted(tss)

    def test_kospi_symbol_and_currency(self):
        p = _provider(_naver_transport(), self.tmp)
        bars = p.daily_history("005930", "KOSPI", refresh=True)
        for b in bars:
            assert b.symbol.ticker == "005930"
            assert b.symbol.market == Market.KOSPI
            assert b.symbol.currency == "KRW"

    def test_kospi_ohlcv_values_correct(self):
        p = _provider(_naver_transport(), self.tmp)
        bars = p.daily_history("005930", "KOSPI", refresh=True)

        # First row: 20230103|130|133|129|131|100000
        b = bars[0]
        assert b.open   == 130.0
        assert b.high   == 133.0
        assert b.low    == 129.0
        assert b.close  == 131.0
        assert b.volume == 100_000

    def test_naver_url_contains_symbol_not_ks_suffix(self):
        """Naver uses bare KRX code, not 005930.KS."""
        captured: list[str] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            captured.append(str(request.url))
            return httpx.Response(200, content=_make_naver_xml().encode())

        transport = httpx.MockTransport(_handler)
        client = httpx.Client(transport=transport)
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)
        p.daily_history("005930", "KOSPI", refresh=True)

        assert len(captured) == 1
        assert "005930" in captured[0]
        assert ".KS" not in captured[0]
        assert "naver" in captured[0]

    def test_naver_non_200_raises_runtime_error(self):
        p = _provider(_naver_transport(status_code=500), self.tmp)
        with pytest.raises(RuntimeError, match="500"):
            p.daily_history("005930", "KOSPI", refresh=True)

    def test_naver_empty_xml_raises_runtime_error(self):
        empty_xml = '<?xml version="1.0"?><protocol><chartdata></chartdata></protocol>'
        p = _provider(_naver_transport(xml=empty_xml), self.tmp)
        with pytest.raises(RuntimeError, match="Malformed|empty"):
            p.daily_history("005930", "KOSPI", refresh=True)

    def test_kospi_timestamps_are_tz_aware(self):
        p = _provider(_naver_transport(), self.tmp)
        bars = p.daily_history("005930", "KOSPI", refresh=True)
        for b in bars:
            assert b.ts.tzinfo is not None


# ---------------------------------------------------------------------------
# 4. Cache — shared behaviour across both markets
# ---------------------------------------------------------------------------

class TestCacheBehaviour:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def _counted_yahoo_transport(self, counter: list[int]) -> httpx.MockTransport:
        payload = _make_yahoo_payload()

        def _handler(request: httpx.Request) -> httpx.Response:
            counter[0] += 1
            return httpx.Response(200, content=json.dumps(payload).encode())

        return httpx.MockTransport(_handler)

    def _counted_naver_transport(self, counter: list[int]) -> httpx.MockTransport:
        def _handler(request: httpx.Request) -> httpx.Response:
            counter[0] += 1
            return httpx.Response(200, content=_make_naver_xml().encode())

        return httpx.MockTransport(_handler)

    def test_second_call_loads_from_cache_not_network_nasdaq(self):
        call_count = [0]
        transport = self._counted_yahoo_transport(call_count)
        client = httpx.Client(transport=transport)
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)

        bars1 = p.daily_history("AAPL", "NASDAQ", refresh=True)
        assert call_count[0] == 1

        bars2 = p.daily_history("AAPL", "NASDAQ", refresh=False)
        assert call_count[0] == 1  # no new network call

        assert len(bars1) == len(bars2)

    def test_second_call_loads_from_cache_not_network_kospi(self):
        call_count = [0]
        transport = self._counted_naver_transport(call_count)
        client = httpx.Client(transport=transport)
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)

        bars1 = p.daily_history("005930", "KOSPI", refresh=True)
        assert call_count[0] == 1

        bars2 = p.daily_history("005930", "KOSPI", refresh=False)
        assert call_count[0] == 1

        assert len(bars1) == len(bars2)

    def test_cache_file_created_after_first_fetch_nasdaq(self):
        p = _provider(_yahoo_transport(_make_yahoo_payload()), self.tmp)
        p.daily_history("AAPL", "NASDAQ", refresh=True)

        cache_path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        assert os.path.exists(cache_path)
        loaded = load_bars(cache_path)
        assert len(loaded) == 3

    def test_cache_file_created_after_first_fetch_kospi(self):
        p = _provider(_naver_transport(), self.tmp)
        p.daily_history("005930", "KOSPI", refresh=True)

        cache_path = os.path.join(self.tmp, "KOSPI_005930.parquet")
        assert os.path.exists(cache_path)
        loaded = load_bars(cache_path)
        assert len(loaded) == 3

    def test_refresh_true_bypasses_existing_cache(self):
        call_count = [0]
        transport = self._counted_yahoo_transport(call_count)
        client = httpx.Client(transport=transport)
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)

        p.daily_history("AAPL", "NASDAQ", refresh=True)
        p.daily_history("AAPL", "NASDAQ", refresh=True)
        assert call_count[0] == 2
