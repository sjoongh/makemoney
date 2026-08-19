# trader/data/index_universe.py
"""RESEARCH ONLY — KOSDAQ150 / NASDAQ100 index universe resolvers.

Free-data expansion Phase 1 (see .omc/specs/deep-interview-free-data-expansion.md).
Pure parsing is separated from HTTP (edgar.py style) so it is fully
unit-testable without network:

  - ``parse_krx_index_constituents``: KRX data portal getJsonData payload
    (bld=dbms/MDC/STAT/standard/MDCSTAT00601, KOSDAQ150) → [(code, name)].
  - ``parse_wikipedia_nasdaq100``: Wikipedia Nasdaq-100 ``constituents``
    table → [(ticker, name)], tickers normalized to yfinance form (dots→dash).
  - ``append_membership_snapshot`` / ``read_membership_snapshots``:
    append-only daily membership jsonl (survivorship-free going FORWARD;
    the historical backfill is current-constituents — see
    docs/data-limitations.md).

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import httpx

# --- HTTP endpoints (fetch layer is thin; parsing above is what's tested) ---
KRX_JSON_URL = "https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
# 지수구성종목 (index constituents) screen; KOSDAQ150 = indTpCd 2 / idxIndCd 203.
KRX_KOSDAQ150_PARAMS = {
    "bld": "dbms/MDC/STAT/standard/MDCSTAT00601",
    "locale": "ko_KR",
    "indIdx": "2",
    "indIdx2": "203",
    "codeNmindIdx_finder_equidx0_0": "코스닥 150",
    "money": "3",
    "csvxls_isNo": "false",
}
# KRX rejects requests without a plausible Referer.
KRX_HEADERS = {
    "Referer": "https://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd",
    "User-Agent": "Mozilla/5.0 (makemoney-research)",
}
# The components table lives on the dedicated list page (NOT /wiki/Nasdaq-100,
# which no longer embeds it — verified 2026-07-27).
WIKI_NASDAQ100_URL = "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"
WIKI_HEADERS = {"User-Agent": "makemoney-research sjh87355@gmail.com"}

# ---------------------------------------------------------------------------
# KRX KOSDAQ150 constituents
# ---------------------------------------------------------------------------

_KRX_CODE_RE = re.compile(r"^\d{6}$")


def parse_krx_index_constituents(payload: dict) -> list[tuple[str, str]]:
    """Parse a KRX getJsonData index-constituents payload → [(code, name)].

    Validates loudly: 6-digit codes, no duplicates, non-empty output.
    """
    output = payload.get("output") or []
    if not output:
        raise ValueError("KRX payload has empty 'output' — wrong bld or params?")
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for rec in output:
        code = str(rec.get("ISU_SRT_CD", "")).strip()
        name = str(rec.get("ISU_ABBRV", "")).strip()
        if not _KRX_CODE_RE.match(code):
            raise ValueError(f"malformed KRX code {code!r} (name={name!r})")
        if code in seen:
            raise ValueError(f"duplicate KRX code {code!r}")
        seen.add(code)
        rows.append((code, name))
    return rows


# ---------------------------------------------------------------------------
# Wikipedia Nasdaq-100 constituents
# ---------------------------------------------------------------------------


class _WikitableParser(HTMLParser):
    """Extract cell-text rows for EVERY table in the document, in order.

    The Nasdaq-100 page (unlike S&P 500) has no ``id="constituents"`` — the
    components table must be found by its header row afterwards.
    """

    def __init__(self) -> None:
        super().__init__()
        self._table_stack: list[list[list[str]]] = []
        self.in_cell = False
        self._row: list[str] = []
        self._cell_parts: list[str] = []
        self.tables: list[list[list[str]]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._table_stack.append([])
        elif self._table_stack and tag == "tr":
            self._row = []
        elif self._table_stack and tag in ("td", "th"):
            self.in_cell = True
            self._cell_parts = []

    def handle_endtag(self, tag):
        if tag == "table" and self._table_stack:
            self.tables.append(self._table_stack.pop())
        elif self._table_stack and tag in ("td", "th"):
            self.in_cell = False
            self._row.append("".join(self._cell_parts).strip())
        elif self._table_stack and tag == "tr" and self._row:
            self._table_stack[-1].append(self._row)

    def handle_data(self, data):
        if self.in_cell:
            self._cell_parts.append(data)


def _components_columns(header: list[str]) -> "tuple[int, int] | None":
    """Return (symbol_idx, company_idx) if this header is the components table."""
    lower = [h.lower() for h in header]
    sym_i = next((i for i, h in enumerate(lower) if h in ("symbol", "ticker")), None)
    name_i = next((i for i, h in enumerate(lower) if "company" in h), None)
    if sym_i is None or name_i is None:
        return None
    return sym_i, name_i


def parse_wikipedia_nasdaq100(html: str) -> list[tuple[str, str]]:
    """Parse the Wikipedia Nasdaq-100 components table → [(ticker, name)].

    The table is located by HEADER CONTENT (Ticker/Symbol + Company), not by
    id — the Nasdaq-100 page has no ``id="constituents"``.
    Tickers are normalized to yfinance form (``BRK.B`` → ``BRK-B``).
    """
    parser = _WikitableParser()
    parser.feed(html)
    for table in parser.tables:
        if not table:
            continue
        cols = _components_columns(table[0])
        if cols is None:
            continue
        sym_i, name_i = cols
        rows: list[tuple[str, str]] = []
        for cells in table[1:]:
            if len(cells) <= max(sym_i, name_i):
                continue
            ticker = cells[sym_i].replace(".", "-").strip()
            name = cells[name_i].strip()
            if ticker:
                rows.append((ticker, name))
        if rows:
            return rows
    raise ValueError("no components table found — Wikipedia layout changed?")


def fetch_kosdaq150(trade_date: str, timeout: float = 20.0) -> list[tuple[str, str]]:
    """Fetch current KOSDAQ150 constituents from KRX (trade_date: YYYYMMDD)."""
    params = dict(KRX_KOSDAQ150_PARAMS, trdDd=trade_date)
    resp = httpx.post(KRX_JSON_URL, data=params, headers=KRX_HEADERS, timeout=timeout)
    resp.raise_for_status()
    return parse_krx_index_constituents(resp.json())


def fetch_nasdaq100(timeout: float = 20.0) -> list[tuple[str, str]]:
    """Fetch current Nasdaq-100 constituents from Wikipedia."""
    resp = httpx.get(
        WIKI_NASDAQ100_URL, headers=WIKI_HEADERS, timeout=timeout, follow_redirects=True
    )
    resp.raise_for_status()
    return parse_wikipedia_nasdaq100(resp.text)


# ---------------------------------------------------------------------------
# Membership snapshots (append-only jsonl, idempotent per date)
# ---------------------------------------------------------------------------


def read_membership_snapshots(path: str | Path) -> list[dict]:
    """Read all membership snapshots ({date, symbols} per line)."""
    p = Path(path)
    if not p.exists():
        return []
    return [
        json.loads(line)
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_membership_snapshot(
    path: str | Path, date: str, symbols: list[str]
) -> bool:
    """Append one daily membership snapshot; no-op if ``date`` already recorded.

    Dates must be appended in ascending order (out-of-order → ValueError).
    Returns True if a line was written, False on idempotent skip.
    """
    if not symbols:
        raise ValueError("empty symbols — refusing to record an empty universe")
    existing = read_membership_snapshots(path)
    if existing:
        last = existing[-1]["date"]
        if date == last or any(s["date"] == date for s in existing):
            return False
        if date < last:
            raise ValueError(f"out-of-order snapshot date {date} < last {last}")
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps({"date": date, "symbols": symbols}, ensure_ascii=False) + "\n")
    return True
