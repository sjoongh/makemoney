# tests/test_fetch_data.py
"""Unit tests for trader.app.fetch_data — no network, fake client."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from trader.core.events import BarEvent, Market, Symbol
from trader.data.storage import load_bars


class _FakeClient:
    """Minimal stand-in for KisClient that returns one hard-coded bar per call."""

    def _one_bar(self, ticker: str, market: str, currency: str) -> list[BarEvent]:
        return [
            BarEvent(
                Symbol(ticker, Market(market), currency),
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                open=1.0,
                high=2.0,
                low=0.5,
                close=1.5,
                volume=100,
            )
        ]

    def daily_bars(
        self,
        ticker: str,
        market: str,
        currency: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[BarEvent]:
        return self._one_bar(ticker, market, currency)

    def daily_bars_history(
        self,
        ticker: str,
        market: str,
        currency: str,
        lookback_days: int = 730,
    ) -> list[BarEvent]:
        return self._one_bar(ticker, market, currency)


def test_fetch_saves_bars(tmp_path):
    from trader.app import fetch_data

    out = str(tmp_path / "bars.parquet")
    n = fetch_data.fetch([("AAPL", "NASDAQ", "USD")], out, client=_FakeClient())
    assert n == 1
    loaded = load_bars(out)
    assert len(loaded) == 1
    assert loaded[0].symbol.ticker == "AAPL"
    assert loaded[0].symbol.market == Market.NASDAQ
    assert loaded[0].symbol.currency == "USD"
    assert loaded[0].close == 1.5


def test_fetch_multiple_symbols(tmp_path):
    from trader.app import fetch_data

    out = str(tmp_path / "multi.parquet")
    syms = [("AAPL", "NASDAQ", "USD"), ("MSFT", "NASDAQ", "USD")]
    n = fetch_data.fetch(syms, out, client=_FakeClient())
    assert n == 2
    loaded = load_bars(out)
    tickers = {b.symbol.ticker for b in loaded}
    assert tickers == {"AAPL", "MSFT"}


def test_fetch_passes_start_end_to_client(tmp_path):
    from trader.app import fetch_data

    captured: list[dict] = []

    class _CapturingClient:
        def daily_bars(self, ticker, market, currency, start=None, end=None):
            captured.append({"ticker": ticker, "start": start, "end": end})
            return [
                BarEvent(
                    Symbol(ticker, Market(market), currency),
                    datetime(2026, 1, 2, tzinfo=timezone.utc),
                    1.0, 2.0, 0.5, 1.5, 100,
                )
            ]

    out = str(tmp_path / "dated.parquet")
    fetch_data.fetch(
        [("AAPL", "NASDAQ", "USD")], out,
        start="20260101", end="20260131",
        client=_CapturingClient(),
    )
    assert captured[0]["start"] == "20260101"
    assert captured[0]["end"] == "20260131"


def test_load_dotenv_sets_missing_keys(tmp_path, monkeypatch):
    from trader.app import fetch_data

    env_file = tmp_path / ".env"
    env_file.write_text("FAKE_KEY_XYZ=hello\nFAKE_KEY_ABC=world\n")

    # Ensure the keys are absent before the call
    monkeypatch.delenv("FAKE_KEY_XYZ", raising=False)
    monkeypatch.delenv("FAKE_KEY_ABC", raising=False)

    fetch_data._load_dotenv(str(env_file))

    import os
    assert os.environ.get("FAKE_KEY_XYZ") == "hello"
    assert os.environ.get("FAKE_KEY_ABC") == "world"


def test_load_dotenv_does_not_overwrite_existing(tmp_path, monkeypatch):
    from trader.app import fetch_data
    import os

    env_file = tmp_path / ".env"
    env_file.write_text("FAKE_EXISTING=from_file\n")

    monkeypatch.setenv("FAKE_EXISTING", "from_env")
    fetch_data._load_dotenv(str(env_file))

    # Pre-existing env var must win
    assert os.environ["FAKE_EXISTING"] == "from_env"


def test_fetch_uses_paginated_history_when_no_start_end(tmp_path):
    """When start/end are omitted, fetch() calls daily_bars_history (paginated path)."""
    from trader.app import fetch_data

    history_calls: list[dict] = []

    class _CapturingHistoryClient:
        def daily_bars_history(self, ticker, market, currency, lookback_days=730):
            history_calls.append({"ticker": ticker, "lookback_days": lookback_days})
            return [
                BarEvent(
                    Symbol(ticker, Market(market), currency),
                    datetime(2026, 1, 2, tzinfo=timezone.utc),
                    1.0, 2.0, 0.5, 1.5, 100,
                )
            ]

    out = str(tmp_path / "hist.parquet")
    n = fetch_data.fetch(
        [("AAPL", "NASDAQ", "USD")], out,
        lookback_days=365,
        client=_CapturingHistoryClient(),
    )
    assert n == 1
    assert len(history_calls) == 1
    assert history_calls[0]["ticker"] == "AAPL"
    assert history_calls[0]["lookback_days"] == 365


def test_fetch_uses_single_page_when_start_and_end_given(tmp_path):
    """When start AND end are given, fetch() uses daily_bars (legacy single-page path)."""
    from trader.app import fetch_data

    daily_calls: list[dict] = []

    class _CapturingDailyClient:
        def daily_bars(self, ticker, market, currency, start=None, end=None):
            daily_calls.append({"ticker": ticker, "start": start, "end": end})
            return [
                BarEvent(
                    Symbol(ticker, Market(market), currency),
                    datetime(2026, 1, 2, tzinfo=timezone.utc),
                    1.0, 2.0, 0.5, 1.5, 100,
                )
            ]

    out = str(tmp_path / "dated.parquet")
    fetch_data.fetch(
        [("AAPL", "NASDAQ", "USD")], out,
        start="20260101", end="20260131",
        client=_CapturingDailyClient(),
    )
    assert len(daily_calls) == 1
    assert daily_calls[0]["start"] == "20260101"
    assert daily_calls[0]["end"] == "20260131"
