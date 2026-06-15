"""Unit tests for KisClient balance inquiry + account_snapshot — MockTransport, no network."""
from __future__ import annotations

import httpx
import pytest

from trader.execution.kis_client import KisClient

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_DOM_BALANCE_RESP = {
    "rt_cd": "0",
    "msg1": "정상처리 되었습니다.",
    "output1": [
        {
            "pdno": "005930",
            "prdt_name": "삼성전자",
            "hldg_qty": "10",
            "prpr": "75000",
            "evlu_amt": "750000",
        }
    ],
    "output2": [
        {
            "dnca_tot_amt": "5000000",
            "prvs_rcdl_excc_amt": "4800000",
            "tot_evlu_amt": "5750000",
        }
    ],
}

_OVR_BALANCE_RESP = {
    "rt_cd": "0",
    "msg1": "정상처리 되었습니다.",
    "output1": [
        {
            "ovrs_pdno": "AAPL",
            "ovrs_item_name": "APPLE",
            "ovrs_cblc_qty": "5",
            "now_pric2": "195.50",
            "evlu_pfls_amt": "50.00",
        }
    ],
    "output2": [{}],
}


def _handler(req: httpx.Request) -> httpx.Response:
    p = str(req.url.path)
    if p.endswith("/oauth2/tokenP"):
        return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
    if "inquire-balance" in p and "domestic-stock" in p:
        return httpx.Response(200, json=_DOM_BALANCE_RESP)
    if "inquire-balance" in p and "overseas-stock" in p:
        return httpx.Response(200, json=_OVR_BALANCE_RESP)
    return httpx.Response(404, json={"error": f"unmatched: {p}"})


def _client(tmp_path) -> KisClient:
    c = httpx.Client(transport=httpx.MockTransport(_handler), base_url="https://mock")
    return KisClient(
        c, "k", "s", "50193330", paper=True, min_interval=0,
        token_cache_path=str(tmp_path / "tok.json"),
    )


# ---------------------------------------------------------------------------
# domestic_balance
# ---------------------------------------------------------------------------

def test_domestic_balance_returns_parsed_body(tmp_path):
    body = _client(tmp_path).domestic_balance()
    assert body["rt_cd"] == "0"
    assert len(body["output1"]) == 1
    assert body["output1"][0]["pdno"] == "005930"
    assert len(body["output2"]) == 1
    assert body["output2"][0]["dnca_tot_amt"] == "5000000"


def test_domestic_balance_raises_on_error(tmp_path):
    def handler_err(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
        return httpx.Response(200, json={"rt_cd": "1", "msg1": "잔고조회 오류"})

    c = httpx.Client(transport=httpx.MockTransport(handler_err), base_url="https://mock")
    kis = KisClient(c, "k", "s", "50193330", paper=True, min_interval=0,
                    token_cache_path=str(tmp_path / "tok.json"))
    with pytest.raises(RuntimeError, match="잔고조회 오류"):
        kis.domestic_balance()


# ---------------------------------------------------------------------------
# overseas_balance
# ---------------------------------------------------------------------------

def test_overseas_balance_returns_parsed_body(tmp_path):
    body = _client(tmp_path).overseas_balance()
    assert body["rt_cd"] == "0"
    assert len(body["output1"]) == 1
    assert body["output1"][0]["ovrs_pdno"] == "AAPL"
    assert body["output1"][0]["ovrs_cblc_qty"] == "5"


# ---------------------------------------------------------------------------
# account_snapshot
# ---------------------------------------------------------------------------

def test_account_snapshot_cash_krw(tmp_path):
    snap = _client(tmp_path).account_snapshot()
    # dnca_tot_amt = "5000000"
    assert snap["cash_krw"] == 5_000_000.0


def test_account_snapshot_domestic_position(tmp_path):
    snap = _client(tmp_path).account_snapshot()
    key = ("KOSPI", "005930")
    assert key in snap["positions"]
    assert snap["positions"][key] == 10
    assert snap["marks"][key] == 75_000.0


def test_account_snapshot_overseas_position(tmp_path):
    snap = _client(tmp_path).account_snapshot()
    key = ("NASDAQ", "AAPL")
    assert key in snap["positions"]
    assert snap["positions"][key] == 5
    assert snap["marks"][key] == 195.50


def test_account_snapshot_shape(tmp_path):
    snap = _client(tmp_path).account_snapshot()
    assert "cash_krw" in snap
    assert "positions" in snap
    assert "marks" in snap
    assert isinstance(snap["cash_krw"], float)
    assert isinstance(snap["positions"], dict)
    assert isinstance(snap["marks"], dict)


def test_account_snapshot_skips_zero_qty_rows(tmp_path):
    """Rows with qty=0 must be excluded from positions."""
    def handler_zero(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})
        if "domestic-stock" in p:
            return httpx.Response(200, json={
                "rt_cd": "0", "msg1": "ok",
                "output1": [{"pdno": "005930", "hldg_qty": "0", "prpr": "75000"}],
                "output2": [{"dnca_tot_amt": "1000000"}],
            })
        if "overseas-stock" in p:
            return httpx.Response(200, json={
                "rt_cd": "0", "msg1": "ok",
                "output1": [{"ovrs_pdno": "AAPL", "ovrs_cblc_qty": "0", "now_pric2": "195"}],
                "output2": [{}],
            })
        return httpx.Response(404, json={})

    c = httpx.Client(transport=httpx.MockTransport(handler_zero), base_url="https://mock")
    kis = KisClient(c, "k", "s", "50193330", paper=True, min_interval=0,
                    token_cache_path=str(tmp_path / "tok.json"))
    snap = kis.account_snapshot()
    assert snap["positions"] == {}
    assert snap["marks"] == {}
    assert snap["cash_krw"] == 1_000_000.0
