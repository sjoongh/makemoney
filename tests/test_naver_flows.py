# tests/test_naver_flows.py
"""R7 (free-data expansion) — Naver per-stock investor-flow parser/store.

Pure parsing on captured-shape fixtures; no network.
"""
from __future__ import annotations

import json

import pytest

from trader.data.naver_flows import parse_naver_frgn, save_flows, load_flows


def _row(date: str, vals: list[str]) -> str:
    tds = [f'<td class="tc"><span class="tah p10 gray03">{date}</span></td>']
    for v in vals:
        tds.append(f'<td class="num"><span class="tah p11">{v}</span></td>')
    return "<tr>" + "".join(tds) + "</tr>"


# 종가 | 전일비 | 등락률 | 거래량 | 기관순매매 | 외인순매매 | 외인보유주수 | 외인보유율
PAGE = f"""
<html><body><table>
<tr><th rowspan="2">날짜</th><th rowspan="2">종가</th></tr>
{_row("2026.08.14", ["274,500", "6,500", "+2.43%", "18,470,000", "+1,352,893", "-1,038,745", "3,067,151,411", "51.38%"])}
{_row("2026.08.13", ["268,000", "12,500", "-1.28%", "21,111,222", "-353,393", "+2,038,745", "3,068,190,156", "51.40%"])}
</table></body></html>
"""


def test_parse_naver_frgn_extracts_rows():
    rows = parse_naver_frgn(PAGE)
    assert rows == [
        {
            "date": "2026-08-14",
            "close": 274500.0,
            "volume": 18470000,
            "inst_net": 1352893,
            "frgn_net": -1038745,
            "frgn_held": 3067151411,
            "frgn_ratio": 51.38,
        },
        {
            "date": "2026-08-13",
            "close": 268000.0,
            "volume": 21111222,
            "inst_net": -353393,
            "frgn_net": 2038745,
            "frgn_held": 3068190156,
            "frgn_ratio": 51.40,
        },
    ]


def test_parse_empty_page_returns_no_rows():
    assert parse_naver_frgn("<html><table></table></html>") == []


def test_parse_rejects_malformed_numeric_row():
    bad = f"<table>{_row('2026.08.14', ['274,500', 'x', '+1%', 'n/a', '?', '?', '?', '?'])}</table>"
    with pytest.raises(ValueError, match="2026.08.14"):
        parse_naver_frgn(bad)


def test_save_and_load_flows_dedupes_by_symbol_date(tmp_path):
    p = tmp_path / "KOSPI_flows.parquet"
    r1 = dict(parse_naver_frgn(PAGE)[0], symbol="005930")
    r2 = dict(parse_naver_frgn(PAGE)[1], symbol="005930")
    n = save_flows(p, [r1, r2], created_ts="2026-08-16T00:00:00+00:00")
    assert n == 2
    # overlapping re-save (updated value wins, no dup)
    n = save_flows(p, [dict(r1, inst_net=999)], created_ts="2026-08-17T00:00:00+00:00")
    assert n == 2
    rows = load_flows(p)
    assert [r["inst_net"] for r in rows if r["date"] == "2026-08-14"] == [999]
    man = json.loads((tmp_path / "KOSPI_flows.parquet.manifest.json").read_text())
    assert man["n_rows"] == 2 and len(man["content_hash"]) == 64


def test_save_flows_rejects_missing_symbol(tmp_path):
    row = dict(parse_naver_frgn(PAGE)[0])  # no symbol
    with pytest.raises(ValueError, match="symbol"):
        save_flows(tmp_path / "f.parquet", [row], created_ts="2026-08-16T00:00:00+00:00")
