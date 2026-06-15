#!/usr/bin/env python3
"""Live read-only verification of domestic_filled_orders (VTTC0081R).

Usage:
    .venv/bin/python scripts/verify_domestic_fills.py

Reads credentials from .env (KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT).
Calls domestic_filled_orders(as_of_yyyymmdd="20260615") and prints the result.
Safe: read-only inquiry, no orders placed.
"""
import os
import sys

import httpx

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trader.execution.kis_client import KisClient

# Load .env manually (no dotenv dependency)
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

APP_KEY = os.environ["KIS_APP_KEY"]
APP_SECRET = os.environ["KIS_APP_SECRET"]
ACCOUNT = os.environ.get("KIS_ACCOUNT", "50193330")
PAPER = os.environ.get("KIS_PAPER", "1") == "1"

BASE_URL = (
    "https://openapivts.koreainvestment.com:29443"
    if PAPER
    else "https://openapi.koreainvestment.com:9443"
)

print(f"[verify] domain: {BASE_URL}")
print(f"[verify] account: {ACCOUNT}  paper={PAPER}")

client = httpx.Client(base_url=BASE_URL, timeout=15)
kis = KisClient(
    client,
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    account=ACCOUNT,
    paper=PAPER,
    min_interval=0.5,
    token_cache_path=".kis_token.json",
)

DATE = "20260615"
print(f"[verify] calling domestic_filled_orders(as_of_yyyymmdd={DATE!r}) ...")

try:
    fills = kis.domestic_filled_orders(as_of_yyyymmdd=DATE)
    print(f"[verify] SUCCESS — rt_cd=0, {len(fills)} fill(s) returned")
    for i, f in enumerate(fills):
        print(f"  fill[{i}]: {f}")
    if not fills:
        print("  (empty list — no domestic trades on that date, as expected)")
except RuntimeError as exc:
    print(f"[verify] RuntimeError: {exc}")
    sys.exit(1)
except Exception as exc:
    print(f"[verify] Unexpected error: {type(exc).__name__}: {exc}")
    sys.exit(1)
