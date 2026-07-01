# trader/data/edgar.py
"""RESEARCH ONLY — POINT-IN-TIME fundamentals from SEC EDGAR XBRL (free).

Unlike yfinance (≈5 quarters, period-end only, retroactively restated), EDGAR's
companyconcept API gives every datapoint with its ACTUAL ``filed`` date and full
history (10-15+ years), so we can build a survivorship/look-ahead-clean
fundamental panel: at signal date ``t`` use only values with ``filed <= t``.

Pure parsing (quarterly assembly, point-in-time accessors) is separated from
HTTP so it is fully unit-testable without network.

NEVER import from live/paper trading or the backtest/live parity path.
SEC policy: requests must send a descriptive User-Agent with contact info and
stay under ~10 req/s.
"""
from __future__ import annotations

import time
from datetime import date, datetime
from typing import Optional

import httpx

SEC_UA = {"User-Agent": "makemoney-research sjh87355@gmail.com"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"

# Equity concept with fallbacks (first present wins).
EQUITY_CONCEPTS = (
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
)
SHARES_CONCEPTS = (
    "CommonStockSharesOutstanding",
    "EntityCommonStockSharesOutstanding",
)


def _d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Pure parsing — quarterly net income (handles YTD vs 3-month + derives Q4)
# ---------------------------------------------------------------------------

def quarterly_series(unit_points: list[dict]) -> list[dict]:
    """Extract a consistent QUARTERLY (3-month) series from companyconcept USD
    duration datapoints.

    Each input point: {start, end, filed, val, form, fp, fy}.
    Returns list of {period_end (date), filed (date), val (float)} — explicit
    3-month quarters plus derived Q4 (FY − sum of that year's 3 quarters).
    Restatements collapse to the ORIGINAL (earliest-filed) value per period_end.
    """
    explicit: dict[date, dict] = {}   # period_end -> original-filed 3-month point
    annual: dict[int, dict] = {}      # fy -> original-filed ~annual point
    by_fy_quarters: dict[int, list] = {}

    for p in unit_points:
        if "start" not in p or "end" not in p or "filed" not in p:
            continue
        try:
            start = _d(p["start"]); end = _d(p["end"]); filed = _d(p["filed"])
            val = float(p["val"]); fy = int(p.get("fy")) if p.get("fy") is not None else None
        except (ValueError, TypeError):
            continue
        span = (end - start).days

        if 80 <= span <= 100:  # ~3-month quarter
            prev = explicit.get(end)
            if prev is None or filed < prev["filed"]:
                explicit[end] = {"period_end": end, "filed": filed, "val": val}
            if fy is not None:
                by_fy_quarters.setdefault(fy, []).append((end, val, filed))
        elif 350 <= span <= 380 and fy is not None:  # ~annual
            prev = annual.get(fy)
            if prev is None or filed < prev["filed"]:
                annual[fy] = {"period_end": end, "filed": filed, "val": val}

    # Derive Q4 = FY − (the 3 explicit quarters of that fiscal year)
    for fy, a in annual.items():
        qs = explicit_quarters_for_fy(explicit, by_fy_quarters, fy, a["period_end"])
        if len(qs) == 3 and a["period_end"] not in explicit:
            q4_val = a["val"] - sum(q["val"] for q in qs)
            explicit[a["period_end"]] = {
                "period_end": a["period_end"],
                "filed": a["filed"],
                "val": q4_val,
            }

    return sorted(explicit.values(), key=lambda r: r["period_end"])


def explicit_quarters_for_fy(explicit, by_fy_quarters, fy, annual_end) -> list[dict]:
    """The 3 explicit 3-month quarters belonging to fiscal year *fy* (period_end
    strictly before the annual period_end)."""
    out = []
    for end, val, filed in by_fy_quarters.get(fy, []):
        if end < annual_end and end in explicit:
            out.append(explicit[end])
    # de-dupe by period_end, keep at most 3 most recent before annual_end
    seen, uniq = set(), []
    for q in sorted(out, key=lambda r: r["period_end"], reverse=True):
        if q["period_end"] in seen:
            continue
        seen.add(q["period_end"]); uniq.append(q)
    return uniq[:3]


# ---------------------------------------------------------------------------
# Pure parsing — instant series (equity, shares)
# ---------------------------------------------------------------------------

def instant_series(unit_points: list[dict]) -> list[dict]:
    """Instant concept (no duration): one value per period_end, original-filed."""
    out: dict[date, dict] = {}
    for p in unit_points:
        if "end" not in p or "filed" not in p:
            continue
        try:
            end = _d(p["end"]); filed = _d(p["filed"]); val = float(p["val"])
        except (ValueError, TypeError):
            continue
        prev = out.get(end)
        if prev is None or filed < prev["filed"]:
            out[end] = {"period_end": end, "filed": filed, "val": val}
    return sorted(out.values(), key=lambda r: r["period_end"])


# ---------------------------------------------------------------------------
# Point-in-time accessors
# ---------------------------------------------------------------------------

def as_of(series: list[dict], t: date) -> Optional[float]:
    """Latest value KNOWN at date *t* (filed <= t), by most-recent period_end."""
    elig = [r for r in series if r["filed"] <= t]
    if not elig:
        return None
    return max(elig, key=lambda r: r["period_end"])["val"]


def sue_as_of(quarterly: list[dict], t: date, *, min_hist: int = 8) -> Optional[float]:
    """Standardized Unexpected Earnings (no analyst estimates) known at *t*.

    Seasonal random walk: expected NI_q = NI_{q-4}. Unexpected = NI_q - NI_{q-4}.
    SUE = latest unexpected / stdev(prior year-over-year NI changes). This is the
    classic estimate-free PEAD signal. Point-in-time: only quarters with
    filed <= t. Needs >= ``min_hist`` filed quarters (so several YoY changes
    exist for the stdev). Returns None otherwise or on zero variance.
    """
    elig = sorted((r for r in quarterly if r["filed"] <= t),
                  key=lambda r: r["period_end"])
    # de-dup by period_end (keep earliest-filed original)
    seen, uniq = set(), []
    for r in elig:
        if r["period_end"] in seen:
            continue
        seen.add(r["period_end"]); uniq.append(r)
    if len(uniq) < min_hist:
        return None
    vals = [r["val"] for r in uniq]
    yoy = [vals[i] - vals[i - 4] for i in range(4, len(vals))]
    if len(yoy) < 2:
        return None
    latest = yoy[-1]
    prior = yoy[:-1]
    mean = sum(prior) / len(prior)          # drift term (Codex): standardize around it
    var = sum((x - mean) ** 2 for x in prior) / (len(prior) - 1) if len(prior) > 1 else 0.0
    sd = var ** 0.5
    if sd == 0:
        return None
    return (latest - mean) / sd             # drift-adjusted SUE


def ttm_as_of(quarterly: list[dict], t: date, n: int = 4) -> Optional[float]:
    """Trailing-n-quarter sum known at *t* (filed <= t). None if < n quarters."""
    elig = sorted((r for r in quarterly if r["filed"] <= t),
                  key=lambda r: r["period_end"], reverse=True)
    # de-dup by period_end
    seen, uniq = set(), []
    for r in elig:
        if r["period_end"] in seen:
            continue
        seen.add(r["period_end"]); uniq.append(r)
    if len(uniq) < n:
        return None
    return sum(r["val"] for r in uniq[:n])


# ---------------------------------------------------------------------------
# HTTP (network) — kept thin
# ---------------------------------------------------------------------------

def ticker_to_cik(client: httpx.Client) -> dict[str, str]:
    r = client.get(TICKERS_URL, headers=SEC_UA)
    r.raise_for_status()
    return {v["ticker"]: str(v["cik_str"]).zfill(10) for v in r.json().values()}


def fetch_concept(client: httpx.Client, cik: str, concept: str) -> list[dict]:
    """Return USD (or shares) unit datapoints for a us-gaap concept, or []."""
    url = CONCEPT_URL.format(cik=cik, concept=concept)
    r = client.get(url, headers=SEC_UA)
    if r.status_code != 200:
        return []
    units = r.json().get("units", {})
    # prefer USD; for share concepts the unit key is "shares"
    for key in ("USD", "shares"):
        if key in units:
            return units[key]
    return next(iter(units.values()), [])


def first_available_concept(client: httpx.Client, cik: str, concepts: tuple) -> list[dict]:
    for c in concepts:
        pts = fetch_concept(client, cik, c)
        if pts:
            return pts
        time.sleep(0.15)  # SEC courtesy throttle
    return []
