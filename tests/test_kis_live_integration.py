"""Live integration tests — hit the real KIS paper API.

Skipped automatically when the .env credential file is absent.
DO NOT loop-hammer the token endpoint; the disk cache handles retries.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.path.exists("/Users/manager/side/makemoney/.env"),
    reason="no KIS .env creds",
)

ENV_PATH = "/Users/manager/side/makemoney/.env"
TOKEN_CACHE = "/Users/manager/side/makemoney/.kis_token.json"
PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"


def _load_env() -> dict:
    env: dict = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _live_client():
    import httpx
    from trader.execution.kis_client import KisClient

    env = _load_env()
    c = httpx.Client(base_url=PAPER_BASE_URL, timeout=20)
    return KisClient(
        c,
        env["KIS_APP_KEY"],
        env["KIS_APP_SECRET"],
        env["KIS_ACCOUNT"],
        paper=True,
        min_interval=0.6,
        token_cache_path=TOKEN_CACHE,
    )


def test_live_overseas_daily_bars():
    """Fetch AAPL daily bars from KIS paper API — must return real data."""
    bars = _live_client().daily_bars("AAPL", "NASDAQ", "USD")
    assert len(bars) > 0, "Expected at least one AAPL bar from KIS"
    assert all(b.close > 0 for b in bars), "All bars must have positive close"
    # Bars must be sorted ascending
    assert [b.ts for b in bars] == sorted(b.ts for b in bars), "Bars must be ascending"
    # Spot-check structure
    bar = bars[0]
    assert bar.symbol.ticker == "AAPL"
    assert bar.symbol.currency == "USD"
    assert bar.open > 0 and bar.high >= bar.low


def test_live_token_cached_after_first_call():
    """Token cache file must exist after a live call.

    A short sleep is added before the API call so that back-to-back test
    execution (each with a fresh client instance whose throttle counter resets
    to 0) does not hit KIS's per-second rate limit.
    """
    import time
    time.sleep(1.0)  # guard against inter-test throttle (500 "초당 거래건수 초과")
    _live_client().daily_bars("AAPL", "NASDAQ", "USD")
    assert os.path.exists(TOKEN_CACHE), "Token cache file should be written"
