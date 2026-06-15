"""Unit tests for KisClient.domestic_filled_orders — MockTransport only.

Covers:
  - Correct endpoint, tr_id (VTTC0081R), and params sent
  - Normalized dict shape: ticker, qty, side (BUY/SELL), market=KOSPI, currency=KRW
  - Domestic side-code mapping: "02"=BUY, "01"=SELL
  - Zero-qty rows skipped
  - rt_cd != "0" raises RuntimeError
  - filled_orders() merges domestic into combined result
"""
from __future__ import annotations

import json

import httpx
import pytest

from trader.execution.kis_client import KisClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(handler, tmp_path):
    c = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://mock")
    return KisClient(
        c,
        app_key="k",
        app_secret="s",
        account="50193330",
        paper=True,
        min_interval=0,
        token_cache_path=str(tmp_path / "tok.json"),
    )


def _token_response():
    return httpx.Response(200, json={"access_token": "TESTTOKEN", "expires_in": 86400})


# Sample domestic output1 row — one BUY fill for 삼성전자 (005930)
_SAMPLE_OUTPUT1 = [
    {
        "odno": "KR0000001",
        "pdno": "005930",
        "sll_buy_dvsn_cd": "02",    # "02" = BUY (domestic)
        "tot_ccld_qty": "10",        # 총체결수량
        "avg_prvs": "71500",         # 평균가 (average price)
        "tot_ccld_amt": "715000",    # 총체결금액 (fallback price source)
    },
    {
        # Unfilled row — should be skipped
        "odno": "KR0000002",
        "pdno": "000660",
        "sll_buy_dvsn_cd": "01",
        "tot_ccld_qty": "0",
        "avg_prvs": "0",
        "tot_ccld_amt": "0",
    },
    {
        "odno": "KR0000003",
        "pdno": "035720",
        "sll_buy_dvsn_cd": "01",    # "01" = SELL (domestic)
        "tot_ccld_qty": "5",
        "avg_prvs": "52000",
        "tot_ccld_amt": "260000",
    },
]


# ---------------------------------------------------------------------------
# Tests: domestic_filled_orders()
# ---------------------------------------------------------------------------

def test_domestic_filled_orders_uses_vttc0081r_tr_id(tmp_path):
    """domestic_filled_orders must send tr_id=VTTC0081R."""
    captured = {}

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-daily-ccld" in p:
            captured["tr_id"] = req.headers.get("tr_id")
            captured["path"] = p
            return httpx.Response(
                200, json={"rt_cd": "0", "msg1": "ok", "output1": []}
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    kis.domestic_filled_orders(as_of_yyyymmdd="20260615")

    assert captured["tr_id"] == "VTTC0081R"
    assert captured["path"] == "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"


def test_domestic_filled_orders_sends_correct_params(tmp_path):
    """domestic_filled_orders must pass the expected query params."""
    captured = {}

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-daily-ccld" in p:
            captured["params"] = dict(req.url.params)
            return httpx.Response(
                200, json={"rt_cd": "0", "msg1": "ok", "output1": []}
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    kis.domestic_filled_orders(as_of_yyyymmdd="20260615")

    p = captured["params"]
    assert p["CANO"] == "50193330"
    assert p["ACNT_PRDT_CD"] == "01"
    assert p["INQR_STRT_DT"] == "20260615"
    assert p["INQR_END_DT"] == "20260615"
    assert p["SLL_BUY_DVSN_CD"] == "00"   # all (buy+sell)
    assert p["CCLD_DVSN"] == "01"          # filled only


def test_domestic_filled_orders_parses_normalized_dicts(tmp_path):
    """Filled rows are returned as normalized dicts with expected field values."""
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-daily-ccld" in p:
            return httpx.Response(
                200,
                json={"rt_cd": "0", "msg1": "ok", "output1": _SAMPLE_OUTPUT1},
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    fills = kis.domestic_filled_orders(as_of_yyyymmdd="20260615")

    # Zero-qty row is skipped → 2 fills
    assert len(fills) == 2

    buy = fills[0]
    assert buy["order_id"] == "KR0000001"
    assert buy["ticker"] == "005930"
    assert buy["market"] == "KOSPI"
    assert buy["currency"] == "KRW"
    assert buy["side"] == "BUY"
    assert buy["qty"] == 10
    assert buy["price"] == 71500.0
    assert buy["commission"] == 0.0

    sell = fills[1]
    assert sell["order_id"] == "KR0000003"
    assert sell["ticker"] == "035720"
    assert sell["market"] == "KOSPI"
    assert sell["currency"] == "KRW"
    assert sell["side"] == "SELL"
    assert sell["qty"] == 5
    assert sell["price"] == 52000.0
    assert sell["commission"] == 0.0


def test_domestic_filled_orders_side_mapping(tmp_path):
    """Domestic side codes: '02'→BUY, '01'→SELL."""
    rows = [
        {"odno": "1", "pdno": "A", "sll_buy_dvsn_cd": "02",
         "tot_ccld_qty": "1", "avg_prvs": "100", "tot_ccld_amt": "100"},
        {"odno": "2", "pdno": "B", "sll_buy_dvsn_cd": "01",
         "tot_ccld_qty": "2", "avg_prvs": "200", "tot_ccld_amt": "400"},
    ]

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-daily-ccld" in p:
            return httpx.Response(200, json={"rt_cd": "0", "msg1": "ok", "output1": rows})
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    fills = kis.domestic_filled_orders(as_of_yyyymmdd="20260615")

    assert fills[0]["side"] == "BUY"
    assert fills[1]["side"] == "SELL"


def test_domestic_filled_orders_price_fallback_to_tot_ccld_amt(tmp_path):
    """When avg_prvs is missing/zero, price is computed from tot_ccld_amt/qty."""
    rows = [
        {
            "odno": "1",
            "pdno": "005930",
            "sll_buy_dvsn_cd": "02",
            "tot_ccld_qty": "4",
            "avg_prvs": "",          # empty → use fallback
            "tot_ccld_amt": "280000",
        }
    ]

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-daily-ccld" in p:
            return httpx.Response(200, json={"rt_cd": "0", "msg1": "ok", "output1": rows})
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    fills = kis.domestic_filled_orders(as_of_yyyymmdd="20260615")

    assert len(fills) == 1
    assert fills[0]["price"] == 70000.0   # 280000 / 4


def test_domestic_filled_orders_skips_zero_qty_rows(tmp_path):
    """Rows with tot_ccld_qty==0 must be excluded from output."""
    rows = [
        {"odno": "1", "pdno": "005930", "sll_buy_dvsn_cd": "02",
         "tot_ccld_qty": "0", "avg_prvs": "70000", "tot_ccld_amt": "0"},
    ]

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-daily-ccld" in p:
            return httpx.Response(200, json={"rt_cd": "0", "msg1": "ok", "output1": rows})
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    fills = kis.domestic_filled_orders(as_of_yyyymmdd="20260615")
    assert fills == []


def test_domestic_filled_orders_raises_on_nonzero_rt_cd(tmp_path):
    """rt_cd != '0' must raise RuntimeError containing the msg1 text."""
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-daily-ccld" in p:
            return httpx.Response(
                200,
                json={"rt_cd": "7", "msg1": "국내체결조회 오류", "output1": []},
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    with pytest.raises(RuntimeError, match="국내체결조회 오류"):
        kis.domestic_filled_orders(as_of_yyyymmdd="20260615")


def test_domestic_filled_orders_empty_list_when_no_fills(tmp_path):
    """Empty output1 returns []."""
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-daily-ccld" in p:
            return httpx.Response(200, json={"rt_cd": "0", "msg1": "ok", "output1": []})
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    assert kis.domestic_filled_orders(as_of_yyyymmdd="20260615") == []


# ---------------------------------------------------------------------------
# Tests: filled_orders() integration — merges both markets
# ---------------------------------------------------------------------------

def test_filled_orders_merges_overseas_and_domestic(tmp_path):
    """filled_orders() returns a combined list of NASDAQ + KOSPI fills."""
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-ccnl" in p:
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "ok",
                    "output": [
                        {
                            "odno": "US001",
                            "pdno": "AAPL",
                            "sll_buy_dvsn_cd": "02",
                            "ft_ccld_qty": "2",
                            "ft_ccld_unpr3": "295.85",
                        }
                    ],
                },
            )
        if "inquire-daily-ccld" in p:
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "ok",
                    "output1": [
                        {
                            "odno": "KR001",
                            "pdno": "005930",
                            "sll_buy_dvsn_cd": "02",
                            "tot_ccld_qty": "10",
                            "avg_prvs": "71500",
                            "tot_ccld_amt": "715000",
                        }
                    ],
                },
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    fills = kis.filled_orders()

    assert len(fills) == 2

    nasdaq_fill = next(f for f in fills if f["market"] == "NASDAQ")
    assert nasdaq_fill["ticker"] == "AAPL"
    assert nasdaq_fill["currency"] == "USD"
    assert nasdaq_fill["side"] == "BUY"
    assert nasdaq_fill["qty"] == 2

    kospi_fill = next(f for f in fills if f["market"] == "KOSPI")
    assert kospi_fill["ticker"] == "005930"
    assert kospi_fill["currency"] == "KRW"
    assert kospi_fill["side"] == "BUY"
    assert kospi_fill["qty"] == 10
    assert kospi_fill["price"] == 71500.0
