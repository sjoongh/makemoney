"""Unit tests for KisClient — uses httpx.MockTransport, no real network."""
import json
import os

import httpx
import pytest

from trader.core.events import BarEvent, Market
from trader.execution.kis_client import KisClient


# ---------------------------------------------------------------------------
# Mock handler
# ---------------------------------------------------------------------------

def _handler(req):
    p = str(req.url.path)
    if p.endswith("/oauth2/tokenP"):
        return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
    if "overseas-price" in p:
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output2": [
                    {
                        "xymd": "20260102",
                        "open": "10",
                        "high": "11",
                        "low": "9",
                        "clos": "10.5",
                        "tvol": "100",
                    },
                    {
                        "xymd": "20260105",
                        "open": "11",
                        "high": "12",
                        "low": "10",
                        "clos": "11.5",
                        "tvol": "200",
                    },
                ],
            },
        )
    if "domestic-stock" in p:
        return httpx.Response(
            200,
            json={
                "rt_cd": "0",
                "msg1": "ok",
                "output2": [
                    {
                        "stck_bsop_date": "20260102",
                        "stck_oprc": "100",
                        "stck_hgpr": "110",
                        "stck_lwpr": "90",
                        "stck_clpr": "105",
                        "acml_vol": "1000",
                    }
                ],
            },
        )
    return httpx.Response(404, json={})


def _client(tmp_path):
    c = httpx.Client(
        transport=httpx.MockTransport(_handler), base_url="https://mock"
    )
    return KisClient(
        c,
        "k",
        "s",
        "50193330",
        paper=True,
        min_interval=0,
        token_cache_path=str(tmp_path / "tok.json"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_overseas_daily_bars_normalize_and_sorted(tmp_path):
    bars = _client(tmp_path).daily_bars("AAPL", "NASDAQ", "USD")
    assert len(bars) == 2
    assert all(isinstance(b, BarEvent) for b in bars)
    # Ascending order
    assert [b.ts for b in bars] == sorted(b.ts for b in bars)
    assert bars[0].close == 10.5
    assert bars[0].symbol.currency == "USD"
    assert bars[0].symbol.market == Market.NASDAQ


def test_domestic_daily_bars_normalize(tmp_path):
    bars = _client(tmp_path).daily_bars("005930", "KOSPI", "KRW")
    assert len(bars) == 1
    assert bars[0].close == 105.0
    assert bars[0].symbol.currency == "KRW"
    assert bars[0].symbol.market == Market.KOSPI


def test_token_is_cached_not_reissued(tmp_path):
    """Two daily_bars calls on the same client must not re-issue the token."""
    c = _client(tmp_path)
    c.daily_bars("AAPL", "NASDAQ", "USD")
    c.daily_bars("AAPL", "NASDAQ", "USD")
    # Cache file must exist (token was persisted)
    assert os.path.exists(str(tmp_path / "tok.json"))
    # Verify cache content is valid JSON with expected fields
    with open(str(tmp_path / "tok.json")) as f:
        cached = json.load(f)
    assert cached["access_token"] == "T"
    assert cached["expires_at"] > 0


def test_disk_token_cache_reused_across_instances(tmp_path):
    """A second KisClient instance should read the token from disk, not re-issue."""
    token_path = str(tmp_path / "tok.json")
    # First client issues token and caches it
    c1 = _client(tmp_path)
    c1.daily_bars("AAPL", "NASDAQ", "USD")
    assert os.path.exists(token_path)

    # Second client — fresh in-memory state, same cache file
    c2 = httpx.Client(transport=httpx.MockTransport(_handler), base_url="https://mock")
    client2 = KisClient(
        c2, "k", "s", "50193330", paper=True, min_interval=0, token_cache_path=token_path
    )
    # Should work from disk cache without hitting /oauth2/tokenP again
    bars = client2.daily_bars("AAPL", "NASDAQ", "USD")
    assert len(bars) == 2


def test_zero_close_rows_skipped(tmp_path):
    """Rows with zero or empty close must be skipped defensively."""

    def handler_with_zero(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
        if "overseas-price" in p:
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "ok",
                    "output2": [
                        # valid row
                        {
                            "xymd": "20260102",
                            "open": "10",
                            "high": "11",
                            "low": "9",
                            "clos": "10.5",
                            "tvol": "100",
                        },
                        # zero close — should be skipped
                        {
                            "xymd": "20260103",
                            "open": "0",
                            "high": "0",
                            "low": "0",
                            "clos": "0",
                            "tvol": "0",
                        },
                        # empty close — should be skipped
                        {
                            "xymd": "20260104",
                            "open": "",
                            "high": "",
                            "low": "",
                            "clos": "",
                            "tvol": "",
                        },
                    ],
                },
            )
        return httpx.Response(404, json={})

    c = httpx.Client(
        transport=httpx.MockTransport(handler_with_zero), base_url="https://mock"
    )
    kis = KisClient(
        c, "k", "s", "50193330", paper=True, min_interval=0,
        token_cache_path=str(tmp_path / "tok.json"),
    )
    bars = kis.daily_bars("AAPL", "NASDAQ", "USD")
    assert len(bars) == 1
    assert bars[0].close == 10.5


def test_non_zero_rt_cd_raises(tmp_path):
    """Non-zero rt_cd must raise RuntimeError with msg1."""

    def handler_err(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
        return httpx.Response(
            200,
            json={"rt_cd": "1", "msg1": "초당 거래건수를 초과하였습니다", "output2": []},
        )

    c = httpx.Client(
        transport=httpx.MockTransport(handler_err), base_url="https://mock"
    )
    kis = KisClient(
        c, "k", "s", "50193330", paper=True, min_interval=0,
        token_cache_path=str(tmp_path / "tok.json"),
    )
    with pytest.raises(RuntimeError, match="초당"):
        kis.daily_bars("AAPL", "NASDAQ", "USD")


def test_submit_order_returns_odno(tmp_path):
    """submit_order calls the overseas order endpoint and returns ODNO."""
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
        if p.endswith("/uapi/overseas-stock/v1/trading/order"):
            return httpx.Response(
                200, json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "0000001"}}
            )
        return httpx.Response(404, json={})

    c = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://mock")
    kis = KisClient(c, "k", "s", "50193330", paper=True, min_interval=0,
                    token_cache_path=str(tmp_path / "tok.json"))
    result = kis.submit_order("AAPL", "NASDAQ", "BUY", 1, price=1.0)
    assert result == "0000001"


def test_filled_orders_returns_empty_list_when_no_fills(tmp_path):
    """filled_orders returns [] when the API reports no executions."""
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
        if "inquire-ccnl" in p:
            return httpx.Response(
                200, json={"rt_cd": "0", "msg1": "ok", "output": []}
            )
        return httpx.Response(404, json={})

    c = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://mock")
    kis = KisClient(c, "k", "s", "50193330", paper=True, min_interval=0,
                    token_cache_path=str(tmp_path / "tok.json"))
    result = kis.filled_orders()
    assert result == []
