# trader/data/edgar_events.py
"""RESEARCH ONLY — POINT-IN-TIME 8-K events from the EDGAR submissions API.

Free-data expansion Phase 3 (see .omc/specs/deep-interview-free-data-expansion.md).
Complements trader/data/edgar.py (XBRL fundamentals) with the submissions
feed: every filing per CIK with its ``acceptanceDateTime`` — the honest
point-in-time timestamp (a Friday-evening 8-K is tradable Monday, not Friday).

Pure parsing/normalization is separated from HTTP (edgar.py style).
NEVER import from live/paper trading or the backtest/live parity path.
SEC policy: descriptive User-Agent, <10 req/s (reuse edgar.SEC_UA).
"""
from __future__ import annotations

import httpx

from trader.data.edgar import SEC_UA

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"

# Columns of filings.recent we consume (columnar arrays, one entry per filing).
_COLUMNS = {
    "accessionNumber": "accession",
    "form": "form",
    "acceptanceDateTime": "accepted_ts",
    "filingDate": "filing_date",
    "items": "items",
    "primaryDocument": "primary_doc",
}


def parse_submissions(payload: dict) -> list[dict]:
    """Parse a submissions API payload → row dicts (all forms, newest first).

    The API is columnar (parallel arrays); ragged lengths mean a truncated
    or malformed download and raise loudly.
    """
    recent = (payload.get("filings") or {}).get("recent")
    if recent is None:
        raise ValueError("payload has no filings.recent — wrong URL or truncated?")
    cols = {out: list(recent.get(src, [])) for src, out in _COLUMNS.items()}
    lengths = {len(v) for v in cols.values()}
    if len(lengths) != 1:
        raise ValueError(f"ragged submissions columns: { {k: len(v) for k, v in cols.items()} }")
    n = lengths.pop()
    return [{k: cols[k][i] for k in cols} for i in range(n)]


def normalize_edgar_events(symbol: str, cik: str, rows: list[dict]) -> list[dict]:
    """Filter to 8-K filings and normalize to the spec §4 events schema.

    event_type = ``8-K:<first item>`` (e.g. ``8-K:2.02`` earnings) so filings
    bucket by their primary item; itemless legacy filings stay plain ``8-K``.
    """
    cik_int = int(cik)
    out: list[dict] = []
    for r in rows:
        # 6-K is the material-event form for foreign private issuers
        # (ASML, PDD, ARM…), which are exempt from 8-K.
        if r["form"] not in ("8-K", "6-K"):
            continue
        accepted = (r.get("accepted_ts") or "").strip()
        if not accepted:
            raise ValueError(f"missing acceptanceDateTime for {r.get('accession')}")
        items = (r.get("items") or "").strip()
        form = r["form"]
        event_type = f"{form}:{items.split(',')[0].strip()}" if items else form
        accession = r["accession"]
        url = ARCHIVE_URL.format(
            cik=cik_int,
            accession_nodash=accession.replace("-", ""),
            doc=r.get("primary_doc", ""),
        )
        out.append(
            {
                "market": "NASDAQ",
                "symbol": symbol,
                "corp": str(cik_int),
                "event_type": event_type,
                "title": f"{form} items {items}" if items else form,
                "accepted_ts": accepted,
                "filing_date": r["filing_date"],
                "source_id": accession,
                "url": url,
            }
        )
    return out


# ---------------------------------------------------------------------------
# thin HTTP fetcher
# ---------------------------------------------------------------------------


def fetch_submissions(cik: str, timeout: float = 30.0) -> list[dict]:
    """Fetch + parse the submissions feed for one CIK."""
    resp = httpx.get(
        SUBMISSIONS_URL.format(cik=int(cik)), headers=SEC_UA, timeout=timeout
    )
    resp.raise_for_status()
    return parse_submissions(resp.json())
