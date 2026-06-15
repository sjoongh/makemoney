# trader/execution/kis_client.py
"""KIS Open API client — paper trading, Phase 1.5.

Operational constraints (from docs/kis-api-reference.md):
  1. Token caching: KIS rate-limits re-issuance (~1/min). Never re-request a valid token.
  2. Throttle: KIS 500s on bursts. Enforce min_interval between every request.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from trader.core.events import BarEvent, Market, Symbol


class KisClient:
    """KIS REST wrapper. Isolates domestic/overseas differences inside.

    Args:
        client: httpx.Client with base_url set (real or MockTransport for tests).
        app_key, app_secret, account: KIS credentials.
        paper: True = paper trading domain (openapivts…).
        min_interval: Minimum seconds between consecutive requests (throttle).
        token_cache_path: Path for JSON token disk cache.
    """

    def __init__(
        self,
        client: httpx.Client,
        app_key: str,
        app_secret: str,
        account: str,
        paper: bool = True,
        min_interval: float = 0.5,
        token_cache_path: str = ".kis_token.json",
    ):
        self._c = client
        self.app_key = app_key
        self.app_secret = app_secret
        self.account = account
        self.paper = paper
        self.min_interval = min_interval
        self.token_cache_path = token_cache_path

        # In-memory token cache
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

        # Throttle: track time of last request
        self._last_request_at: float = 0.0

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """Return a valid access token, using cache where possible."""
        now = time.time()

        # 1) In-memory cache
        if self._token and now < self._token_expires_at:
            return self._token

        # 2) Disk cache
        if os.path.exists(self.token_cache_path):
            try:
                with open(self.token_cache_path) as f:
                    cached = json.load(f)
                if now < cached.get("expires_at", 0):
                    self._token = cached["access_token"]
                    self._token_expires_at = cached["expires_at"]
                    return self._token
            except (json.JSONDecodeError, KeyError, OSError):
                pass  # corrupt cache — fall through to re-issue

        # 3) Issue new token (counts against KIS rate limit)
        self._throttle()
        resp = self._c.post(
            "/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        expires_in = int(data.get("expires_in", 86400))
        expires_at = now + expires_in - 600  # 10-min safety margin

        # Store in memory
        self._token = token
        self._token_expires_at = expires_at

        # Persist to disk
        try:
            with open(self.token_cache_path, "w") as f:
                json.dump({"access_token": token, "expires_at": expires_at}, f)
        except OSError:
            pass  # disk write failure is non-fatal

        return token

    # ------------------------------------------------------------------
    # Throttle
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep if needed to honour min_interval between requests."""
        if self.min_interval <= 0:
            return
        elapsed = time.time() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_at = time.time()

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------

    def _headers(self, tr_id: str) -> dict:
        token = self._get_token()
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def daily_bars(
        self,
        ticker: str,
        market: str,
        currency: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> list[BarEvent]:
        """Fetch daily OHLCV bars sorted ascending by timestamp.

        Args:
            ticker: e.g. "AAPL" or "005930".
            market: "NASDAQ" or "KOSPI".
            currency: "USD" or "KRW".
            start: YYYYMMDD (used by domestic; ignored for overseas).
            end: YYYYMMDD (used by both; empty string = most recent).
        """
        sym = Symbol(ticker, Market(market), currency)

        if market == "NASDAQ":
            bars = self._daily_bars_overseas(sym, ticker, end)
        elif market == "KOSPI":
            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            bars = self._daily_bars_domestic(
                sym, ticker, start or "20240101", end or today_str
            )
        else:
            raise ValueError(f"Unsupported market: {market}")

        # Sort ascending by timestamp
        bars.sort(key=lambda b: b.ts)
        return bars

    # ------------------------------------------------------------------
    # Overseas (NASDAQ)
    # ------------------------------------------------------------------

    def _daily_bars_overseas(
        self, sym: Symbol, ticker: str, end: Optional[str]
    ) -> list[BarEvent]:
        self._throttle()
        resp = self._c.get(
            "/uapi/overseas-price/v1/quotations/dailyprice",
            headers=self._headers("HHDFS76240000"),
            params={
                "AUTH": "",
                "EXCD": "NAS",
                "SYMB": ticker,
                "GUBN": "0",
                "BYMD": end or "",
                "MODP": "0",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS overseas daily_bars error: {body.get('msg1', body)}"
            )

        bars: list[BarEvent] = []
        for row in body.get("output2", []):
            close_val = row.get("clos", "")
            if not close_val or float(close_val) == 0:
                continue
            ts = datetime.strptime(row["xymd"], "%Y%m%d").replace(tzinfo=timezone.utc)
            bars.append(
                BarEvent(
                    symbol=sym,
                    ts=ts,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(close_val),
                    volume=int(row.get("tvol", 0)),
                )
            )
        return bars

    # ------------------------------------------------------------------
    # Domestic (KOSPI)
    # ------------------------------------------------------------------

    def _daily_bars_domestic(
        self, sym: Symbol, ticker: str, start: str, end: str
    ) -> list[BarEvent]:
        self._throttle()
        resp = self._c.get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            headers=self._headers("FHKST03010100"),
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker,
                "FID_INPUT_DATE_1": start,
                "FID_INPUT_DATE_2": end,
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "0",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS domestic daily_bars error: {body.get('msg1', body)}"
            )

        bars: list[BarEvent] = []
        for row in body.get("output2", []):
            close_val = row.get("stck_clpr", "")
            if not close_val or float(close_val) == 0:
                continue
            ts = datetime.strptime(row["stck_bsop_date"], "%Y%m%d").replace(
                tzinfo=timezone.utc
            )
            bars.append(
                BarEvent(
                    symbol=sym,
                    ts=ts,
                    open=float(row["stck_oprc"]),
                    high=float(row["stck_hgpr"]),
                    low=float(row["stck_lwpr"]),
                    close=float(close_val),
                    volume=int(row.get("acml_vol", 0)),
                )
            )
        return bars

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(
        self,
        ticker: str,
        market: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "00",
    ) -> str:
        """Submit a paper order and return the broker order id (ODNO).

        Args:
            ticker: e.g. "AAPL" or "005930".
            market: "NASDAQ" or "KOSPI".
            side: "BUY" or "SELL".
            quantity: Number of shares.
            price: Limit price (0.0 for market orders on KOSPI).
            order_type: KIS ORD_DVSN code — "00" limit / "01" market.
                        For NASDAQ paper trading only limit ("00") is supported.
                        For KOSPI default is "01" (market); caller may override.

        Returns:
            ODNO (broker order number) as a string.

        Raises:
            RuntimeError: if rt_cd != "0" in the KIS response.
        """
        if market == "NASDAQ":
            tr_id = "VTTT1002U" if side == "BUY" else "VTTT1006U"
            path = "/uapi/overseas-stock/v1/trading/order"
            body = {
                "CANO": self.account,
                "ACNT_PRDT_CD": "01",
                "OVRS_EXCG_CD": "NASD",
                "PDNO": ticker,
                "ORD_QTY": str(quantity),
                "OVRS_ORD_UNPR": str(price),
                "ORD_DVSN": order_type,
                "ORD_SVR_DVSN_CD": "0",
            }
        elif market == "KOSPI":
            tr_id = "VTTC0012U" if side == "BUY" else "VTTC0011U"
            path = "/uapi/domestic-stock/v1/trading/order-cash"
            # KOSPI default: market order ("01"); caller may pass "00" for limit
            kospi_ord_dvsn = order_type if order_type != "00" else "01"
            body = {
                "CANO": self.account,
                "ACNT_PRDT_CD": "01",
                "PDNO": ticker,
                "ORD_DVSN": kospi_ord_dvsn,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(int(price)),
                "EXCG_ID_DVSN_CD": "KRX",
            }
        else:
            raise ValueError(f"Unsupported market: {market}")

        self._throttle()
        resp = self._c.post(path, headers=self._headers(tr_id), json=body)
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS submit_order error [{data.get('rt_cd')}]: {data.get('msg1', data)}"
            )

        output = data.get("output", {})
        odno = output.get("ODNO", "")
        return odno

    # ------------------------------------------------------------------
    # Fill inquiry
    # ------------------------------------------------------------------

    def filled_orders(self) -> list[dict]:
        """Query today's overseas (NASDAQ) executions.

        Returns a list of dicts with keys:
            order_id, ticker, market, currency, side,
            qty, price, commission

        Domestic fill inquiry is a TODO stub (returns []).
        Only rows with executed qty > 0 are included.

        KIS overseas side codes: "02" = BUY, "01" = SELL.
        """
        today = datetime.now(timezone.utc).strftime("%Y%m%d")

        self._throttle()
        resp = self._c.get(
            "/uapi/overseas-stock/v1/trading/inquire-ccnl",
            headers=self._headers("VTTS3035R"),
            params={
                "CANO": self.account,
                "ACNT_PRDT_CD": "01",
                "PDNO": "",
                "ORD_STRT_DT": today,
                "ORD_END_DT": today,
                "SLL_BUY_DVSN": "00",
                "CCLD_NCCS_DVSN": "00",
                "OVRS_EXCG_CD": "",
                "SORT_SQN": "DS",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
                "ORD_DT": "",
                "ORD_GNO_BRNO": "",
                "ODNO": "",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS filled_orders error [{data.get('rt_cd')}]: {data.get('msg1', data)}"
            )

        fills: list[dict] = []
        _side_map = {"02": "BUY", "01": "SELL"}

        for row in data.get("output", []):
            filled_qty_raw = row.get("ft_ccld_qty", "0")
            try:
                filled_qty = int(filled_qty_raw)
            except (ValueError, TypeError):
                filled_qty = 0
            if filled_qty <= 0:
                continue  # skip unfilled / zero rows

            sll_buy_code = row.get("sll_buy_dvsn_cd", "")
            side_str = _side_map.get(sll_buy_code, sll_buy_code)

            fills.append(
                {
                    "order_id": row.get("odno", ""),
                    "ticker": row.get("pdno", ""),
                    "market": "NASDAQ",
                    "currency": "USD",
                    "side": side_str,
                    "qty": filled_qty,
                    "price": float(row.get("ft_ccld_unpr3", "0") or "0"),
                    "commission": 0.0,
                }
            )

        # TODO: domestic (KOSPI) fill inquiry — VTTC0081R — not yet implemented
        return fills

    # ------------------------------------------------------------------
    # Balance inquiry
    # ------------------------------------------------------------------

    def domestic_balance(self) -> dict:
        """GET /uapi/domestic-stock/v1/trading/inquire-balance (VTTC8434R paper).

        Returns the parsed JSON body with:
          output1: list of position rows (pdno, hldg_qty, prpr, ...)
          output2: list with one summary row (dnca_tot_amt = 예수금총금액,
                   prvs_rcdl_excc_amt = 전일매도정산금 — we use dnca_tot_amt
                   as available KRW cash; see account_snapshot docstring).

        Raises RuntimeError if rt_cd != "0".
        """
        cano = self.account
        self._throttle()
        resp = self._c.get(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            headers=self._headers("VTTC8434R"),
            params={
                "CANO": cano,
                "ACNT_PRDT_CD": "01",
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "00",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS domestic_balance error [{body.get('rt_cd')}]: {body.get('msg1', body)}"
            )
        return body

    def overseas_balance(self, exchange: str = "NASD", ccy: str = "USD") -> dict:
        """GET /uapi/overseas-stock/v1/trading/inquire-balance (VTTS3012R paper).

        Args:
            exchange: KIS exchange code e.g. "NASD" (NASDAQ).
            ccy: Currency code e.g. "USD".

        Returns the parsed JSON body with:
          output1: list of position rows (ovrs_pdno, ovrs_cblc_qty, now_pric2, ...)

        Raises RuntimeError if rt_cd != "0".
        """
        cano = self.account
        self._throttle()
        resp = self._c.get(
            "/uapi/overseas-stock/v1/trading/inquire-balance",
            headers=self._headers("VTTS3012R"),
            params={
                "CANO": cano,
                "ACNT_PRDT_CD": "01",
                "OVRS_EXCG_CD": exchange,
                "TR_CRCY_CD": ccy,
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("rt_cd") != "0":
            raise RuntimeError(
                f"KIS overseas_balance error [{body.get('rt_cd')}]: {body.get('msg1', body)}"
            )
        return body

    def account_snapshot(self) -> dict:
        """Return a normalized account snapshot combining domestic + overseas balances.

        Structure:
            {
                "cash_krw": float,            # KRW available cash (dnca_tot_amt from domestic output2)
                "positions": {(market, ticker): qty},   # int qty; market is "KOSPI" or "NASDAQ"
                "marks":     {(market, ticker): price}, # float last price in native currency
            }

        Cash note: we use `dnca_tot_amt` (예수금총금액 — total deposit amount) from
        domestic output2[0] as the base KRW cash figure.  This is the gross available
        cash before settlement netting; it is the most reliably present field across
        KIS paper accounts.  Overseas USD cash is a TODO (folded later via FX).

        Defensively casts all string fields to float/int; skips zero-qty rows.
        """
        dom = self.domestic_balance()
        ovr = self.overseas_balance()

        # --- KRW cash ---
        dom_summary = dom.get("output2", [{}])
        summary_row = dom_summary[0] if dom_summary else {}
        cash_krw = _safe_float(summary_row.get("dnca_tot_amt", "0"))

        positions: dict[tuple[str, str], int] = {}
        marks: dict[tuple[str, str], float] = {}

        # --- Domestic positions (KOSPI) ---
        for row in dom.get("output1", []):
            ticker = row.get("pdno", "").strip()
            qty = _safe_int(row.get("hldg_qty", "0"))
            price = _safe_float(row.get("prpr", "0"))
            if not ticker or qty == 0:
                continue
            key = ("KOSPI", ticker)
            positions[key] = qty
            marks[key] = price

        # --- Overseas positions (NASDAQ) ---
        for row in ovr.get("output1", []):
            ticker = row.get("ovrs_pdno", "").strip()
            qty = _safe_int(row.get("ovrs_cblc_qty", "0"))
            price = _safe_float(row.get("now_pric2", "0"))
            if not ticker or qty == 0:
                continue
            key = ("NASDAQ", ticker)
            positions[key] = qty
            marks[key] = price

        return {
            "cash_krw": cash_krw,
            "positions": positions,
            "marks": marks,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val, default: float = 0.0) -> float:
    """Cast string/number to float; return default on failure."""
    try:
        return float(val) if val not in (None, "", "-") else default
    except (ValueError, TypeError):
        return default


def _safe_int(val, default: int = 0) -> int:
    """Cast string/number to int; return default on failure."""
    try:
        return int(float(val)) if val not in (None, "", "-") else default
    except (ValueError, TypeError):
        return default
