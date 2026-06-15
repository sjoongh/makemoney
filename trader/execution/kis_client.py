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
    # Order stubs (implemented in a later task)
    # ------------------------------------------------------------------

    def submit_order(
        self, ticker: str, market: str, side: str, quantity: int
    ) -> str:
        """Stub — order submission implemented in a later task."""
        return ""

    def filled_orders(self) -> list[dict]:
        """Stub — fill query implemented in a later task."""
        return []
