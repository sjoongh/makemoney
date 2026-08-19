# trader/data/dart.py
"""RESEARCH ONLY — POINT-IN-TIME disclosure events from DART OpenAPI (free).

Free-data expansion Phase 2 (see .omc/specs/deep-interview-free-data-expansion.md).
Pure parsing/normalization is separated from HTTP (edgar.py style) so it is
fully unit-testable without network.

Point-in-time discipline: the event timestamp is the ACCEPTANCE date
(``rcept_dt``, ordered by ``rcept_no``) — never the period/event date.
Effective-date computation (first bar OPEN strictly after acceptance) is done
downstream against the trading calendar, not here.

DART hard limits: 20,000 requests/day/key. ``DartBudget`` enforces a
self-imposed cap BELOW that so a runaway backfill can never exhaust the key.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import httpx

DART_BASE = "https://opendart.fss.or.kr/api"
CORPCODE_URL = f"{DART_BASE}/corpCode.xml"
LIST_URL = f"{DART_BASE}/list.json"
VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

# DART list.json status codes that mean "empty result", not failure.
_NO_DATA_STATUS = "013"
_OK_STATUS = "000"

_RCEPT_DT_RE = re.compile(r"^\d{8}$")
# Leading bracket tags on report names: [기재정정], [첨부추가], [자진공시] …
_PREFIX_TAG_RE = re.compile(r"^(?:\[[^\]]+\])+")
# Trailing parenthetical detail: 주요사항보고서(유상증자결정) → 주요사항보고서
_DETAIL_RE = re.compile(r"\(.*\)$")


# ---------------------------------------------------------------------------
# corpCode.xml → {stock_code: corp_code} (listed companies only)
# ---------------------------------------------------------------------------


def parse_corp_codes(zip_bytes: bytes) -> dict[str, str]:
    """Parse the corpCode.xml zip → {6-digit stock_code: 8-digit corp_code}."""
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        xml = zf.read("CORPCODE.xml")
    root = ElementTree.fromstring(xml)
    mapping: dict[str, str] = {}
    for node in root.iter("list"):
        stock = (node.findtext("stock_code") or "").strip()
        corp = (node.findtext("corp_code") or "").strip()
        if stock and corp:
            mapping[stock] = corp
    if not mapping:
        raise ValueError("no listed companies in corpCode.xml — corrupt download?")
    return mapping


# ---------------------------------------------------------------------------
# list.json page parsing
# ---------------------------------------------------------------------------


def parse_list_page(payload: dict) -> tuple[list[dict], int]:
    """Parse one list.json page → (records, total_pages).

    Status 013 (no data) is a legitimate empty result; any other non-000
    status raises loudly (rate-limit 020, bad key 010/011, …).
    """
    status = str(payload.get("status", ""))
    if status == _NO_DATA_STATUS:
        return [], 0
    if status != _OK_STATUS:
        raise ValueError(f"DART list.json status {status}: {payload.get('message')}")
    return list(payload.get("list", [])), int(payload.get("total_page", 1))


# ---------------------------------------------------------------------------
# normalization → event rows (spec §4 events schema)
# ---------------------------------------------------------------------------


def normalize_dart_events(records: list[dict], *, market: str) -> list[dict]:
    """Normalize raw list.json records → event rows; unlisted filers dropped.

    event_type = report_nm with correction-tag prefixes and parenthetical
    detail stripped, so e.g. every flavor of 주요사항보고서 buckets together.
    """
    rows: list[dict] = []
    for rec in records:
        symbol = str(rec.get("stock_code", "")).strip()
        if not symbol:
            continue  # unlisted filer (fund, private co) — not in our universe
        rcept_dt = str(rec.get("rcept_dt", "")).strip()
        if not _RCEPT_DT_RE.match(rcept_dt):
            raise ValueError(f"malformed rcept_dt {rcept_dt!r} (rcept_no={rec.get('rcept_no')})")
        title = str(rec.get("report_nm", "")).strip()
        event_type = _DETAIL_RE.sub("", _PREFIX_TAG_RE.sub("", title)).strip()
        rcept_no = str(rec.get("rcept_no", "")).strip()
        rows.append(
            {
                "market": market,
                "symbol": symbol,
                "corp": str(rec.get("corp_code", "")).strip(),
                "event_type": event_type,
                "title": title,
                # Date granularity only (DART list API has no intraday time);
                # field named accepted_ts for cross-market schema consistency.
                "accepted_ts": f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:]}",
                "source_id": rcept_no,
                "url": VIEWER_URL.format(rcept_no=rcept_no),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# thin HTTP fetchers (parsing above is what's unit-tested)
# ---------------------------------------------------------------------------


def fetch_corp_codes(api_key: str, timeout: float = 60.0) -> dict[str, str]:
    """Download + parse the full corp-code registry (one ~2MB zip request)."""
    resp = httpx.get(CORPCODE_URL, params={"crtfc_key": api_key}, timeout=timeout)
    resp.raise_for_status()
    return parse_corp_codes(resp.content)


def fetch_list_page(
    api_key: str,
    corp_code: str,
    bgn_de: str,
    end_de: str,
    page_no: int = 1,
    page_count: int = 100,
    timeout: float = 30.0,
) -> tuple[list[dict], int]:
    """Fetch one list.json page for one corp (dates: YYYYMMDD)."""
    resp = httpx.get(
        LIST_URL,
        params={
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_no": str(page_no),
            "page_count": str(page_count),
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return parse_list_page(resp.json())


# ---------------------------------------------------------------------------
# request budget — persisted daily counter, resumable backfill's backstop
# ---------------------------------------------------------------------------


class DartBudget:
    """Persisted per-day request counter; ``try_spend`` returns False at cap.

    The ledger survives process restarts so a resumed backfill on the same
    day continues against the same budget.
    """

    def __init__(self, path: str | Path, daily_cap: int = 15_000) -> None:
        self._path = Path(path)
        self._cap = daily_cap

    def _load(self) -> dict:
        if self._path.exists():
            return json.loads(self._path.read_text(encoding="utf-8"))
        return {}

    def spent(self, day: str) -> int:
        rec = self._load()
        return int(rec.get("count", 0)) if rec.get("day") == day else 0

    def try_spend(self, day: str, n: int = 1) -> bool:
        rec = self._load()
        count = int(rec.get("count", 0)) if rec.get("day") == day else 0
        if count + n > self._cap:
            return False
        self._path.write_text(
            json.dumps({"day": day, "count": count + n}), encoding="utf-8"
        )
        return True
