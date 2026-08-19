# tests/test_dart_events.py
"""Phase 2 (free-data expansion) — DART disclosure events client.

Pure parsing / normalization / budget-ledger tests; no network.
See .omc/specs/deep-interview-free-data-expansion.md.
"""
from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from trader.data.dart import (
    DartBudget,
    normalize_dart_events,
    parse_corp_codes,
    parse_list_page,
)

# ---------------------------------------------------------------------------
# corpCode.xml (zip of CORPCODE.xml) → {stock_code: corp_code}
# ---------------------------------------------------------------------------

CORPCODE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<result>
  <list>
    <corp_code>00126380</corp_code>
    <corp_name>삼성전자</corp_name>
    <stock_code>005930</stock_code>
    <modify_date>20260101</modify_date>
  </list>
  <list>
    <corp_code>00256598</corp_code>
    <corp_name>에코프로비엠</corp_name>
    <stock_code>247540</stock_code>
    <modify_date>20260101</modify_date>
  </list>
  <list>
    <corp_code>00999999</corp_code>
    <corp_name>비상장기업</corp_name>
    <stock_code> </stock_code>
    <modify_date>20260101</modify_date>
  </list>
</result>
"""


def _corp_zip() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("CORPCODE.xml", CORPCODE_XML)
    return buf.getvalue()


def test_parse_corp_codes_maps_listed_only():
    mapping = parse_corp_codes(_corp_zip())
    assert mapping == {"005930": "00126380", "247540": "00256598"}


def test_parse_corp_codes_rejects_empty():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("CORPCODE.xml", "<result></result>")
    with pytest.raises(ValueError, match="no listed"):
        parse_corp_codes(buf.getvalue())


# ---------------------------------------------------------------------------
# list.json page → raw records; error statuses raise
# ---------------------------------------------------------------------------

LIST_PAGE = {
    "status": "000",
    "message": "정상",
    "page_no": 1,
    "total_page": 2,
    "list": [
        {
            "corp_code": "00256598",
            "corp_name": "에코프로비엠",
            "stock_code": "247540",
            "report_nm": "주요사항보고서(유상증자결정)",
            "rcept_no": "20260727000123",
            "flr_nm": "에코프로비엠",
            "rcept_dt": "20260727",
            "rm": "",
        }
    ],
}


def test_parse_list_page_returns_records_and_total_pages():
    records, total_pages = parse_list_page(LIST_PAGE)
    assert total_pages == 2
    assert records[0]["rcept_no"] == "20260727000123"


def test_parse_list_page_no_data_is_empty_not_error():
    # status 013 = 조회된 데이터가 없습니다 — legitimate empty, not a failure.
    records, total_pages = parse_list_page({"status": "013", "message": "없음"})
    assert records == [] and total_pages == 0


def test_parse_list_page_error_status_raises():
    with pytest.raises(ValueError, match="020"):
        parse_list_page({"status": "020", "message": "요청 제한을 초과"})


# ---------------------------------------------------------------------------
# normalization → event rows (point-in-time schema)
# ---------------------------------------------------------------------------


def test_normalize_dart_events_schema():
    rows = normalize_dart_events(LIST_PAGE["list"], market="KOSPI")
    assert rows == [
        {
            "market": "KOSPI",
            "symbol": "247540",
            "corp": "00256598",
            "event_type": "주요사항보고서",
            "title": "주요사항보고서(유상증자결정)",
            "accepted_ts": "2026-07-27",
            "source_id": "20260727000123",
            "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260727000123",
        }
    ]


def test_normalize_skips_unlisted_and_counts_nothing_silently():
    recs = [dict(LIST_PAGE["list"][0]), dict(LIST_PAGE["list"][0], stock_code=" ")]
    rows = normalize_dart_events(recs, market="KOSDAQ")
    assert len(rows) == 1  # unlisted filer dropped


def test_normalize_event_type_strips_correction_prefix():
    rec = dict(LIST_PAGE["list"][0], report_nm="[기재정정]최대주주변경  ")
    rows = normalize_dart_events([rec], market="KOSDAQ")
    assert rows[0]["event_type"] == "최대주주변경"
    assert rows[0]["title"] == "[기재정정]최대주주변경"


def test_normalize_rejects_malformed_rcept_dt():
    rec = dict(LIST_PAGE["list"][0], rcept_dt="2026-07-27")  # must be YYYYMMDD
    with pytest.raises(ValueError, match="rcept_dt"):
        normalize_dart_events([rec], market="KOSDAQ")


# ---------------------------------------------------------------------------
# request budget (20k/day hard API cap → we stop well before it)
# ---------------------------------------------------------------------------


def test_budget_spends_and_blocks_at_cap(tmp_path):
    b = DartBudget(tmp_path / "ledger.json", daily_cap=3)
    assert b.try_spend("2026-07-27") is True
    assert b.try_spend("2026-07-27") is True
    assert b.try_spend("2026-07-27") is True
    assert b.try_spend("2026-07-27") is False  # cap reached


def test_budget_resets_on_new_day(tmp_path):
    b = DartBudget(tmp_path / "ledger.json", daily_cap=1)
    assert b.try_spend("2026-07-27") is True
    assert b.try_spend("2026-07-27") is False
    assert b.try_spend("2026-07-28") is True


def test_budget_persists_across_instances(tmp_path):
    path = tmp_path / "ledger.json"
    b1 = DartBudget(path, daily_cap=2)
    assert b1.try_spend("2026-07-27") is True
    b2 = DartBudget(path, daily_cap=2)
    assert b2.try_spend("2026-07-27") is True
    b3 = DartBudget(path, daily_cap=2)
    assert b3.try_spend("2026-07-27") is False
