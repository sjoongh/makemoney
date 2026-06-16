# tests/test_universe.py
"""Tests for trader/data/universe.py — NO network calls (MockTransport)."""
from __future__ import annotations

import httpx
import pytest

from trader.data.universe import (
    KOSPI_LARGECAP,
    _SP500_FALLBACK,
    load_sp500,
    universe,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_CSV = """\
Symbol,Name,Sector
AAPL,Apple Inc,Information Technology
MSFT,Microsoft Corp,Information Technology
BRK.B,Berkshire Hathaway B,Financials
GOOGL,Alphabet Inc,Communication Services
AMZN,Amazon.com Inc,Consumer Discretionary
"""


class _MockTransport(httpx.BaseTransport):
    """Returns a fixed response for any request."""

    def __init__(self, text: str, status_code: int = 200) -> None:
        self._text = text
        self._status_code = status_code

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=self._status_code,
            text=self._text,
        )


def _client(text: str, status_code: int = 200) -> httpx.Client:
    return httpx.Client(transport=_MockTransport(text, status_code))


# ---------------------------------------------------------------------------
# load_sp500 tests
# ---------------------------------------------------------------------------

class TestLoadSp500:
    def test_parses_csv_and_returns_tickers(self):
        tickers = load_sp500(client=_client(_SAMPLE_CSV))
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert "GOOGL" in tickers

    def test_dot_normalised_to_dash(self):
        """BRK.B must be normalised to BRK-B for Yahoo Finance."""
        tickers = load_sp500(client=_client(_SAMPLE_CSV))
        assert "BRK-B" in tickers
        assert "BRK.B" not in tickers

    def test_returns_all_sample_rows(self):
        tickers = load_sp500(client=_client(_SAMPLE_CSV))
        assert len(tickers) == 5

    def test_fallback_on_http_error(self):
        """Non-200 status must trigger fallback list, not raise."""
        tickers = load_sp500(client=_client("", status_code=503))
        assert tickers == _SP500_FALLBACK

    def test_fallback_on_empty_csv(self):
        """Empty or header-only CSV must trigger fallback, not raise."""
        tickers = load_sp500(client=_client("Symbol,Name,Sector\n"))
        assert tickers == _SP500_FALLBACK

    def test_fallback_on_network_error(self):
        """Connection errors must trigger fallback, not propagate."""

        class _ErrorTransport(httpx.BaseTransport):
            def handle_request(self, request):
                raise httpx.ConnectError("connection refused")

        bad_client = httpx.Client(transport=_ErrorTransport())
        tickers = load_sp500(client=bad_client)
        assert tickers == _SP500_FALLBACK


# ---------------------------------------------------------------------------
# KOSPI_LARGECAP constant
# ---------------------------------------------------------------------------

class TestKospiLargecap:
    def test_contains_samsung(self):
        assert "005930" in KOSPI_LARGECAP

    def test_all_six_digit_strings(self):
        for code in KOSPI_LARGECAP:
            assert len(code) == 6 and code.isdigit(), f"Bad code: {code!r}"

    def test_at_least_20_symbols(self):
        assert len(KOSPI_LARGECAP) >= 20


# ---------------------------------------------------------------------------
# universe() tests
# ---------------------------------------------------------------------------

class TestUniverse:
    def _patched_universe(self, us_limit=120, kr=True):
        """Call universe() but inject a mock client via monkeypatching."""
        # We patch load_sp500 at module level to avoid real HTTP
        import trader.data.universe as umod
        original = umod.load_sp500

        def _fake_load(client=None):
            return load_sp500(client=_client(_SAMPLE_CSV))

        umod.load_sp500 = _fake_load
        try:
            return universe(us_limit=us_limit, kr=kr)
        finally:
            umod.load_sp500 = original

    def test_returns_list_of_tuples(self):
        result = self._patched_universe()
        assert isinstance(result, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in result)

    def test_us_symbols_tagged_nasdaq(self):
        result = self._patched_universe(kr=False)
        assert all(market == "NASDAQ" for _, market in result)

    def test_kr_symbols_tagged_kospi(self):
        result = self._patched_universe(us_limit=0, kr=True)
        assert all(market == "KOSPI" for _, market in result)

    def test_us_limit_respected(self):
        """With us_limit=2, only 2 US symbols should appear."""
        result = self._patched_universe(us_limit=2, kr=False)
        us = [(t, m) for t, m in result if m == "NASDAQ"]
        assert len(us) == 2

    def test_kr_false_excludes_kospi(self):
        result = self._patched_universe(kr=False)
        assert not any(m == "KOSPI" for _, m in result)

    def test_kr_true_includes_kospi(self):
        result = self._patched_universe(us_limit=0, kr=True)
        kospi = [(t, m) for t, m in result if m == "KOSPI"]
        assert len(kospi) == len(KOSPI_LARGECAP)

    def test_brk_b_normalised(self):
        result = self._patched_universe(kr=False)
        tickers = [t for t, _ in result]
        assert "BRK-B" in tickers
        assert "BRK.B" not in tickers
