"""News provider protocol and implementations."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Protocol

from trader.signals.news.models import NewsItem


class NewsProvider(Protocol):
    def fetch_as_of(
        self, symbol: str, as_of: datetime, lookback: timedelta
    ) -> list[NewsItem]:
        """Return items where as_of - lookback <= published_at <= as_of.

        This contract enforces NO look-ahead: items published AFTER as_of
        are never returned.
        """
        ...


class MockNewsProvider:
    """In-memory provider for testing.  Enforces look-ahead safety."""

    def __init__(self, items: list[NewsItem]) -> None:
        self._items = items

    def fetch_as_of(
        self, symbol: str, as_of: datetime, lookback: timedelta
    ) -> list[NewsItem]:
        earliest = as_of - lookback
        filtered = [
            item
            for item in self._items
            if item.symbol == symbol
            and earliest <= item.published_at <= as_of
        ]
        return sorted(filtered, key=lambda x: x.published_at)


class LiveFinnhubProvider:
    """Live Finnhub news provider — skeleton pending API key."""

    # TODO: wire to https://finnhub.io/docs/api/company-news once API key is
    # injected via FINNHUB_API_KEY env var.  Use client kwarg for DI in tests.

    def __init__(self, api_key: str, client=None) -> None:
        self._api_key = api_key
        self._client = client

    def fetch_as_of(
        self, symbol: str, as_of: datetime, lookback: timedelta
    ) -> list[NewsItem]:
        raise NotImplementedError("live provider pending API key")


class LiveDartProvider:
    """Live DART (Korean disclosure) provider — skeleton pending API key."""

    # TODO: wire to https://opendart.fss.or.kr/ once DART_API_KEY is available.
    # Use rcept_dt (접수시각) conservatively as published_at.

    def __init__(self, api_key: str, client=None) -> None:
        self._api_key = api_key
        self._client = client

    def fetch_as_of(
        self, symbol: str, as_of: datetime, lookback: timedelta
    ) -> list[NewsItem]:
        raise NotImplementedError("live provider pending API key")
