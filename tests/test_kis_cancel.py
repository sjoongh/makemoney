"""Unit tests for KisClient.cancel_order — MockTransport only.

Do NOT place or cancel any live orders. All tests use httpx.MockTransport.
"""
from __future__ import annotations

import json

import httpx
import pytest

from trader.execution.kis_client import KisClient


# ---------------------------------------------------------------------------
# Helpers (mirror pattern from test_kis_orders.py)
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


def _cancel_ok_response(odno: str = "CANCEL-001"):
    return httpx.Response(
        200,
        json={
            "rt_cd": "0",
            "msg1": "모의투자 취소 완료",
            "output": {"ODNO": odno},
        },
    )


# ---------------------------------------------------------------------------
# NASDAQ cancel tests
# ---------------------------------------------------------------------------


def test_nasdaq_cancel_posts_to_overseas_rvsecncl(tmp_path):
    """NASDAQ cancel hits /uapi/overseas-stock/v1/trading/order-rvsecncl."""
    captured = {}

    def handler(req):
        if req.url.path.endswith("/oauth2/tokenP"):
            return _token_response()
        if "overseas-stock" in req.url.path and "order-rvsecncl" in req.url.path:
            captured["path"] = req.url.path
            captured["tr_id"] = req.headers.get("tr_id")
            captured["body"] = json.loads(req.content)
            return _cancel_ok_response("NASDAQ-CANCEL-001")
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    result = kis.cancel_order(
        market="NASDAQ",
        original_odno="0000123456",
        ticker="AAPL",
        quantity=5,
    )

    assert result == "NASDAQ-CANCEL-001"
    assert captured["path"] == "/uapi/overseas-stock/v1/trading/order-rvsecncl"


def test_nasdaq_cancel_uses_vttt1004u(tmp_path):
    """NASDAQ cancel uses tr_id VTTT1004U.

    Note: mock-tested only — live-verify when market open.
    """
    captured = {}

    def handler(req):
        if req.url.path.endswith("/oauth2/tokenP"):
            return _token_response()
        if "order-rvsecncl" in req.url.path:
            captured["tr_id"] = req.headers.get("tr_id")
            return _cancel_ok_response()
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    kis.cancel_order(market="NASDAQ", original_odno="111", ticker="AAPL", quantity=1)

    assert captured["tr_id"] == "VTTT1004U"


def test_nasdaq_cancel_body_fields(tmp_path):
    """NASDAQ cancel body has RVSE_CNCL_DVSN_CD='02', ORGN_ODNO, and required fields."""
    captured = {}

    def handler(req):
        if req.url.path.endswith("/oauth2/tokenP"):
            return _token_response()
        if "order-rvsecncl" in req.url.path:
            captured["body"] = json.loads(req.content)
            return _cancel_ok_response()
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    kis.cancel_order(
        market="NASDAQ",
        original_odno="0000123456",
        ticker="TSLA",
        quantity=3,
    )

    body = captured["body"]
    assert body["CANO"] == "50193330"
    assert body["ACNT_PRDT_CD"] == "01"
    assert body["OVRS_EXCG_CD"] == "NASD"
    assert body["PDNO"] == "TSLA"
    assert body["ORGN_ODNO"] == "0000123456"
    assert body["RVSE_CNCL_DVSN_CD"] == "02"  # 02 = cancel
    assert body["ORD_QTY"] == "3"
    assert body["OVRS_ORD_UNPR"] == "0"
    assert body["ORD_SVR_DVSN_CD"] == "0"


# ---------------------------------------------------------------------------
# KOSPI cancel tests
# ---------------------------------------------------------------------------


def test_kospi_cancel_posts_to_domestic_rvsecncl(tmp_path):
    """KOSPI cancel hits /uapi/domestic-stock/v1/trading/order-rvsecncl."""
    captured = {}

    def handler(req):
        if req.url.path.endswith("/oauth2/tokenP"):
            return _token_response()
        if "domestic-stock" in req.url.path and "order-rvsecncl" in req.url.path:
            captured["path"] = req.url.path
            captured["tr_id"] = req.headers.get("tr_id")
            captured["body"] = json.loads(req.content)
            return _cancel_ok_response("KR-CANCEL-001")
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    result = kis.cancel_order(
        market="KOSPI",
        original_odno="6321",
        ticker="005930",
        quantity=10,
    )

    assert result == "KR-CANCEL-001"
    assert captured["path"] == "/uapi/domestic-stock/v1/trading/order-rvsecncl"


def test_kospi_cancel_uses_vttc0013u(tmp_path):
    """KOSPI cancel uses tr_id VTTC0013U.

    Note: mock-tested only — live-verify when market open.
    """
    captured = {}

    def handler(req):
        if req.url.path.endswith("/oauth2/tokenP"):
            return _token_response()
        if "order-rvsecncl" in req.url.path:
            captured["tr_id"] = req.headers.get("tr_id")
            return _cancel_ok_response()
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    kis.cancel_order(market="KOSPI", original_odno="6321", ticker="005930", quantity=1)

    assert captured["tr_id"] == "VTTC0013U"


def test_kospi_cancel_body_fields(tmp_path):
    """KOSPI cancel body has RVSE_CNCL_DVSN_CD='02', ORGN_ODNO, QTY_ALL_ORD_YN='Y'."""
    captured = {}

    def handler(req):
        if req.url.path.endswith("/oauth2/tokenP"):
            return _token_response()
        if "order-rvsecncl" in req.url.path:
            captured["body"] = json.loads(req.content)
            return _cancel_ok_response()
        return httpx.Response(404, json={})

    kis = _make_client(handler, tmp_path)
    kis.cancel_order(
        market="KOSPI",
        original_odno="6321",
        ticker="005930",
        quantity=10,
        order_branch="91252",
    )

    body = captured["body"]
    assert body["CANO"] == "50193330"
    assert body["ACNT_PRDT_CD"] == "01"
    assert body["KRX_FWDG_ORD_ORGNO"] == "91252"
    assert body["ORGN_ODNO"] == "6321"
    assert body["ORD_DVSN"] == "00"
    assert body["RVSE_CNCL_DVSN_CD"] == "02"  # 02 = cancel
    assert body["ORD_QTY"] == "10"
    assert body["ORD_UNPR"] == "0"
    assert body["QTY_ALL_ORD_YN"] == "Y"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_cancel_raises_on_nonzero_rt_cd_nasdaq(tmp_path):
    """cancel_order raises RuntimeError when KIS returns rt_cd != '0' (NASDAQ)."""

    def handler(req):
        if req.url.path.endswith("/oauth2/tokenP"):
            return _token_response()
        return httpx.Response(
            200,
            json={"rt_cd": "1", "msg1": "취소 오류: 원주문 없음", "output": {}},
        )

    kis = _make_client(handler, tmp_path)
    with pytest.raises(RuntimeError, match="취소 오류"):
        kis.cancel_order(
            market="NASDAQ", original_odno="NONEXISTENT", ticker="AAPL", quantity=1
        )


def test_cancel_raises_on_nonzero_rt_cd_kospi(tmp_path):
    """cancel_order raises RuntimeError when KIS returns rt_cd != '0' (KOSPI)."""

    def handler(req):
        if req.url.path.endswith("/oauth2/tokenP"):
            return _token_response()
        return httpx.Response(
            200,
            json={"rt_cd": "7", "msg1": "취소 불가", "output": {}},
        )

    kis = _make_client(handler, tmp_path)
    with pytest.raises(RuntimeError, match="취소 불가"):
        kis.cancel_order(
            market="KOSPI", original_odno="6321", ticker="005930", quantity=5
        )
