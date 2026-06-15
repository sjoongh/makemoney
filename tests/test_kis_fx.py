# tests/test_kis_fx.py
"""Mock tests for KisClient.present_balance and usd_krw_rate (VTRP6504R)."""
from __future__ import annotations

import httpx
import pytest

from trader.execution.kis_client import KisClient


# ---------------------------------------------------------------------------
# Mock transport helpers
# ---------------------------------------------------------------------------

def _token_resp():
    return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})


def _make_client(handler, tmp_path) -> KisClient:
    c = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://mock")
    return KisClient(
        c, "k", "s", "50193330",
        paper=True, min_interval=0,
        token_cache_path=str(tmp_path / "tok.json"),
    )


def _present_balance_handler(output1=None, output2=None, rt_cd="0"):
    """Build a mock handler that returns a present_balance response."""
    def handler(req):
        p = str(req.url.path)
        if p.endswith("/oauth2/tokenP"):
            return _token_resp()
        if "inquire-present-balance" in p:
            return httpx.Response(200, json={
                "rt_cd": rt_cd,
                "msg1": "ok" if rt_cd == "0" else "error",
                "output1": output1 or [],
                "output2": output2 or [],
            })
        return httpx.Response(404, json={})
    return handler


# ---------------------------------------------------------------------------
# Tests: present_balance
# ---------------------------------------------------------------------------

class TestPresentBalance:
    def test_returns_parsed_json(self, tmp_path):
        """present_balance returns the parsed JSON body on rt_cd=0."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": "1375.50"}]
        )
        kis = _make_client(handler, tmp_path)
        result = kis.present_balance()
        assert result["rt_cd"] == "0"
        assert result["output2"][0]["crcy_cd"] == "USD"

    def test_raises_on_nonzero_rt_cd(self, tmp_path):
        """present_balance raises RuntimeError when rt_cd != 0."""
        handler = _present_balance_handler(rt_cd="1")
        kis = _make_client(handler, tmp_path)
        with pytest.raises(RuntimeError, match="present_balance error"):
            kis.present_balance()


# ---------------------------------------------------------------------------
# Tests: usd_krw_rate
# ---------------------------------------------------------------------------

class TestUsdKrwRate:
    def test_reads_from_output2_frst_bltn_exrt(self, tmp_path):
        """usd_krw_rate reads frst_bltn_exrt from output2 when output1 has no USD row."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": "1375.50"}]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate()
        assert rate == 1375.50

    def test_reads_from_output1_bass_exrt_first(self, tmp_path):
        """usd_krw_rate prefers output1.bass_exrt over output2."""
        handler = _present_balance_handler(
            output1=[{"crcy_cd": "USD", "bass_exrt": "1390.00"}],
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": "1375.50"}],
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate()
        assert rate == 1390.00

    def test_skips_non_usd_rows_in_output2(self, tmp_path):
        """Non-USD rows are ignored; only USD row is used."""
        handler = _present_balance_handler(
            output2=[
                {"crcy_cd": "JPY", "frst_bltn_exrt": "0.0065"},
                {"crcy_cd": "USD", "frst_bltn_exrt": "1375.50"},
            ]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate()
        assert rate == 1375.50

    def test_returns_default_when_output_empty(self, tmp_path):
        """Returns default=1380.0 when both output1 and output2 are empty."""
        handler = _present_balance_handler(output1=[], output2=[])
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_returns_default_when_no_usd_row(self, tmp_path):
        """Returns default when no USD currency row exists."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "JPY", "frst_bltn_exrt": "0.0065"}]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_returns_default_when_rate_is_zero(self, tmp_path):
        """Zero exchange rate falls through to default."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": "0"}]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_returns_default_when_rate_is_empty_string(self, tmp_path):
        """Empty string exchange rate falls through to default."""
        handler = _present_balance_handler(
            output2=[{"crcy_cd": "USD", "frst_bltn_exrt": ""}]
        )
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_returns_default_when_api_raises(self, tmp_path):
        """If present_balance raises, usd_krw_rate catches and returns default."""
        handler = _present_balance_handler(rt_cd="1")
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1380.0)
        assert rate == 1380.0

    def test_custom_default(self, tmp_path):
        """Caller-supplied default is respected."""
        handler = _present_balance_handler(output1=[], output2=[])
        kis = _make_client(handler, tmp_path)
        rate = kis.usd_krw_rate(default=1400.0)
        assert rate == 1400.0
