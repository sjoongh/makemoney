# trader/app/fetch_data.py
"""Fetch real KIS daily bars for a symbol universe and save to parquet.

Usage (CLI):
    python -m trader.app.fetch_data <out.parquet> [TICKER:MARKET:CCY ...]

Example:
    python -m trader.app.fetch_data /tmp/aapl.parquet AAPL:NASDAQ:USD
"""
from __future__ import annotations

import os

import httpx

from trader.app.config import AppConfig
from trader.data.storage import save_bars
from trader.execution.kis_client import KisClient

PAPER_BASE = "https://openapivts.koreainvestment.com:29443"


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader — sets missing keys into os.environ, no extra deps."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def build_client() -> KisClient:
    """Build a KisClient from .env / environment variables."""
    if "KIS_APP_KEY" not in os.environ:
        _load_dotenv()
    cfg = AppConfig.from_env()
    c = httpx.Client(base_url=PAPER_BASE, timeout=20)
    return KisClient(
        c,
        cfg.kis_app_key,
        cfg.kis_app_secret,
        cfg.kis_account,
        paper=cfg.paper,
        min_interval=0.6,
    )


def fetch(
    symbols: list[tuple[str, str, str]],
    out_path: str,
    start: str | None = None,
    end: str | None = None,
    client: KisClient | None = None,
) -> int:
    """Fetch daily bars for *symbols* and write parquet to *out_path*.

    Args:
        symbols: List of (ticker, market, currency) tuples.
        out_path: Destination parquet file path.
        start: Optional start date YYYYMMDD (domestic markets only).
        end: Optional end date YYYYMMDD.
        client: Optional pre-built client (useful for testing). Defaults to
                build_client() when None.

    Returns:
        Total number of bars saved.
    """
    if client is None:
        client = build_client()

    bars = []
    for ticker, market, currency in symbols:
        bars.extend(client.daily_bars(ticker, market, currency, start=start, end=end))

    save_bars(bars, out_path)
    return len(bars)


if __name__ == "__main__":
    import sys

    # usage: python -m trader.app.fetch_data <out.parquet> [TICKER:MARKET:CCY ...]
    out = sys.argv[1]
    syms = [tuple(s.split(":")) for s in sys.argv[2:]] or [("AAPL", "NASDAQ", "USD")]
    n = fetch(syms, out)
    print(f"saved {n} bars to {out}")
