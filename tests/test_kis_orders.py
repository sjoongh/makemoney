"""Unit tests for KisClient.submit_order and filled_orders — MockTransport only."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from trader.execution.kis_client import KisClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")


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


# ---------------------------------------------------------------------------
# Test (a): NASDAQ BUY — overseas order path, correct tr_id and body, returns ODNO
# ---------------------------------------------------------------------------

def test_nasdaq_buy_posts_overseas_order_and_returns_odno(tmp_path):
    captured = {}

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if p.endswith("/uapi/overseas-stock/v1/trading/order"):
            captured["path"] = p
            captured["tr_id"] = req.headers.get("tr_id")
            captured["body"] = json.loads(req.content)
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "모의투자 주문 완료",
                    "output": {"ODNO": "0000123456", "ORD_TMD": "093000"},
                },
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    result = kis.submit_order("AAPL", "NASDAQ", "BUY", 5, price=150.0)

    assert result == "0000123456"
    assert captured["tr_id"] == "VTTT1002U"
    assert captured["path"] == "/uapi/overseas-stock/v1/trading/order"

    body = captured["body"]
    assert body["CANO"] == "50193330"
    assert body["ACNT_PRDT_CD"] == "01"
    assert body["OVRS_EXCG_CD"] == "NASD"
    assert body["PDNO"] == "AAPL"
    assert body["ORD_QTY"] == "5"
    assert body["OVRS_ORD_UNPR"] == "150.0"
    assert body["ORD_DVSN"] == "00"
    assert body["ORD_SVR_DVSN_CD"] == "0"


def test_nasdaq_sell_uses_vttt1006u(tmp_path):
    captured = {}

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if p.endswith("/uapi/overseas-stock/v1/trading/order"):
            captured["tr_id"] = req.headers.get("tr_id")
            return httpx.Response(
                200,
                json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "9999"}},
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    result = kis.submit_order("AAPL", "NASDAQ", "SELL", 3, price=200.0)
    assert result == "9999"
    assert captured["tr_id"] == "VTTT1001U"  # paper US sell (VTTT1006U is rejected by KIS paper)


# ---------------------------------------------------------------------------
# Test (b): KOSPI BUY — order-cash path, correct tr_id VTTC0012U
# ---------------------------------------------------------------------------

def test_kospi_buy_posts_order_cash_with_vttc0012u(tmp_path):
    captured = {}

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if p.endswith("/uapi/domestic-stock/v1/trading/order-cash"):
            captured["path"] = p
            captured["tr_id"] = req.headers.get("tr_id")
            captured["body"] = json.loads(req.content)
            return httpx.Response(
                200,
                json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "KR0001"}},
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    result = kis.submit_order("005930", "KOSPI", "BUY", 10, price=70000.0)

    assert result == "KR0001"
    assert captured["tr_id"] == "VTTC0012U"
    assert captured["path"] == "/uapi/domestic-stock/v1/trading/order-cash"

    body = captured["body"]
    assert body["CANO"] == "50193330"
    assert body["ACNT_PRDT_CD"] == "01"
    assert body["PDNO"] == "005930"
    assert body["ORD_QTY"] == "10"
    assert body["ORD_UNPR"] == "70000"
    assert body["EXCG_ID_DVSN_CD"] == "KRX"


def test_kospi_sell_uses_vttc0011u(tmp_path):
    captured = {}

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if p.endswith("/uapi/domestic-stock/v1/trading/order-cash"):
            captured["tr_id"] = req.headers.get("tr_id")
            return httpx.Response(
                200,
                json={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "KR0002"}},
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    result = kis.submit_order("005930", "KOSPI", "SELL", 5, price=70000.0)
    assert result == "KR0002"
    assert captured["tr_id"] == "VTTC0011U"


# ---------------------------------------------------------------------------
# Test (c): filled_orders parses overseas inquire-ccnl into expected dict shape
# ---------------------------------------------------------------------------

def test_filled_orders_parses_overseas_ccnl_response(tmp_path):
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-ccnl" in p:
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "정상처리 되었습니다",
                    "output": [
                        {
                            "odno": "0000123456",
                            "pdno": "AAPL",
                            "sll_buy_dvsn_cd": "02",   # "02" = BUY
                            "ft_ccld_qty": "5",
                            "ft_ccld_unpr3": "150.25",
                            "ovrs_excg_cd": "NASD",
                        },
                        {
                            # Unfilled row — should be skipped
                            "odno": "0000123457",
                            "pdno": "TSLA",
                            "sll_buy_dvsn_cd": "01",
                            "ft_ccld_qty": "0",
                            "ft_ccld_unpr3": "0",
                            "ovrs_excg_cd": "NASD",
                        },
                        {
                            "odno": "0000123458",
                            "pdno": "MSFT",
                            "sll_buy_dvsn_cd": "01",   # "01" = SELL
                            "ft_ccld_qty": "3",
                            "ft_ccld_unpr3": "420.00",
                            "ovrs_excg_cd": "NASD",
                        },
                    ],
                },
            )
        if "inquire-daily-ccld" in p:
            # domestic returns empty — this test is scoped to overseas parsing only
            return httpx.Response(
                200, json={"rt_cd": "0", "msg1": "ok", "output1": []}
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    fills = kis.filled_orders()

    # Only 2 rows have filled qty > 0
    assert len(fills) == 2

    buy_fill = fills[0]
    assert buy_fill["order_id"] == "0000123456"
    assert buy_fill["ticker"] == "AAPL"
    assert buy_fill["market"] == "NASDAQ"
    assert buy_fill["currency"] == "USD"
    assert buy_fill["side"] == "BUY"
    assert buy_fill["qty"] == 5
    assert buy_fill["price"] == 150.25
    assert buy_fill["commission"] == 0.0

    sell_fill = fills[1]
    assert sell_fill["order_id"] == "0000123458"
    assert sell_fill["ticker"] == "MSFT"
    assert sell_fill["side"] == "SELL"
    assert sell_fill["qty"] == 3
    assert sell_fill["price"] == 420.00


def test_filled_orders_uses_vtts3035r_tr_id(tmp_path):
    captured = {}

    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-ccnl" in p:
            captured["tr_id"] = req.headers.get("tr_id")
            return httpx.Response(
                200,
                json={"rt_cd": "0", "msg1": "ok", "output": []},
            )
        if "inquire-daily-ccld" in p:
            return httpx.Response(
                200, json={"rt_cd": "0", "msg1": "ok", "output1": []}
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    kis.filled_orders()
    assert captured["tr_id"] == "VTTS3035R"


def test_filled_orders_empty_when_no_fills(tmp_path):
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        if "inquire-ccnl" in p:
            return httpx.Response(
                200, json={"rt_cd": "0", "msg1": "ok", "output": []}
            )
        if "inquire-daily-ccld" in p:
            return httpx.Response(
                200, json={"rt_cd": "0", "msg1": "ok", "output1": []}
            )
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    assert kis.filled_orders() == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_submit_order_raises_on_nonzero_rt_cd(tmp_path):
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        return httpx.Response(
            200,
            json={"rt_cd": "1", "msg1": "주문 오류", "output": {}},
        )

    kis = _make_client(handler, tmp_path)
    with pytest.raises(RuntimeError, match="주문 오류"):
        kis.submit_order("AAPL", "NASDAQ", "BUY", 1, price=1.0)


def test_filled_orders_raises_on_nonzero_rt_cd(tmp_path):
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_response()
        return httpx.Response(
            200,
            json={"rt_cd": "7", "msg1": "조회 오류", "output": []},
        )

    kis = _make_client(handler, tmp_path)
    with pytest.raises(RuntimeError, match="조회 오류"):
        kis.filled_orders()
