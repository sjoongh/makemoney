# trader/data/fred.py
"""RESEARCH ONLY — keyless macro series from FRED (St. Louis Fed).

The public fredgraph CSV endpoint needs no API key:
    https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y2Y

Used for macro REGIME conditioning of cross-sectional signals (e.g. yield-curve
slope T10Y2Y, VIX). Pure parsing is separated from HTTP for unit testing.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import httpx

CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def parse_fred_csv(text: str) -> list[tuple[date, float]]:
    """Parse FRED CSV → ascending [(date, value)], skipping missing ('.'/'')."""
    out: list[tuple[date, float]] = []
    lines = text.splitlines()
    for line in lines[1:]:  # skip header
        parts = line.split(",")
        if len(parts) < 2:
            continue
        d_str, v_str = parts[0].strip(), parts[1].strip()
        if v_str in ("", "."):
            continue
        try:
            out.append((datetime.strptime(d_str, "%Y-%m-%d").date(), float(v_str)))
        except ValueError:
            continue
    out.sort(key=lambda r: r[0])
    return out


def fetch_series(client: httpx.Client, series_id: str) -> list[tuple[date, float]]:
    r = client.get(CSV_URL.format(series_id=series_id), follow_redirects=True)
    r.raise_for_status()
    return parse_fred_csv(r.text)


def as_of_value(series: list[tuple[date, float]], t: date) -> Optional[float]:
    """Latest macro value KNOWN at date *t* (observation date <= t).

    Macro series are released same/next day, so observation-date alignment is a
    reasonable point-in-time proxy (no deep restatement issue for these series).
    """
    val: Optional[float] = None
    for d, v in series:  # ascending
        if d <= t:
            val = v
        else:
            break
    return val
