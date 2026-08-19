# tests/test_index_universe.py
"""Phase 1 (free-data expansion) — index universe resolvers.

Pure-parsing tests on captured-shape fixtures; no network.
See .omc/specs/deep-interview-free-data-expansion.md.
"""
from __future__ import annotations

import json

import pytest

from trader.data.index_universe import (
    append_membership_snapshot,
    parse_krx_index_constituents,
    parse_wikipedia_nasdaq100,
    read_membership_snapshots,
)

# ---------------------------------------------------------------------------
# KRX KOSDAQ150 constituents (data.krx.co.kr getJsonData response shape)
# ---------------------------------------------------------------------------

KRX_PAYLOAD = {
    "output": [
        {"ISU_SRT_CD": "247540", "ISU_ABBRV": "에코프로비엠", "MKTCAP": "1"},
        {"ISU_SRT_CD": "086520", "ISU_ABBRV": "에코프로", "MKTCAP": "2"},
        {"ISU_SRT_CD": "028300", "ISU_ABBRV": "HLB", "MKTCAP": "3"},
    ],
    "CURRENT_DATETIME": "2026.07.27 PM 04:00:00",
}


def test_parse_krx_constituents_returns_code_name_pairs():
    rows = parse_krx_index_constituents(KRX_PAYLOAD)
    assert rows == [
        ("247540", "에코프로비엠"),
        ("086520", "에코프로"),
        ("028300", "HLB"),
    ]


def test_parse_krx_rejects_malformed_code():
    bad = {"output": [{"ISU_SRT_CD": "24754", "ISU_ABBRV": "짧은코드"}]}
    with pytest.raises(ValueError, match="24754"):
        parse_krx_index_constituents(bad)


def test_parse_krx_rejects_duplicate_codes():
    dup = {
        "output": [
            {"ISU_SRT_CD": "247540", "ISU_ABBRV": "에코프로비엠"},
            {"ISU_SRT_CD": "247540", "ISU_ABBRV": "중복"},
        ]
    }
    with pytest.raises(ValueError, match="duplicate"):
        parse_krx_index_constituents(dup)


def test_parse_krx_rejects_empty_output():
    with pytest.raises(ValueError, match="empty"):
        parse_krx_index_constituents({"output": []})


# ---------------------------------------------------------------------------
# Wikipedia Nasdaq-100 constituents table
# ---------------------------------------------------------------------------

# Real Nasdaq-100 page has NO id="constituents" (unlike the S&P 500 page);
# tables carry generic parser ids (mwXg, ...). The components table must be
# found by its header (Ticker/Symbol + Company), not by id.
WIKI_HTML = """
<html><body>
<table class="wikitable" id="mwXg"><tbody>
<tr><th>Year</th><th>Value</th></tr>
<tr><td>2020</td><td>IGNORED</td></tr>
</tbody></table>
<table class="wikitable" id="mwAU4">
<tbody>
<tr><th>Ticker</th><th>Company</th><th>GICS Sector</th></tr>
<tr><td>AAPL</td><td><a href="/wiki/Apple_Inc.">Apple Inc.</a></td><td>Information Technology</td></tr>
<tr><td>NVDA</td><td><a href="/wiki/Nvidia">Nvidia</a></td><td>Information Technology</td></tr>
<tr><td>BRK.B</td><td>Fake Dotted</td><td>Financials</td></tr>
</tbody>
</table>
</body></html>
"""


def test_parse_wikipedia_nasdaq100_finds_components_table_by_header():
    rows = parse_wikipedia_nasdaq100(WIKI_HTML)
    assert ("AAPL", "Apple Inc.") in rows
    assert ("NVDA", "Nvidia") in rows
    assert all(sym != "IGNORED" for sym, _ in rows)
    assert all(sym != "2020" for sym, _ in rows)


def test_parse_wikipedia_nasdaq100_normalizes_dotted_tickers_for_yfinance():
    # BRK.B style tickers must be yfinance-compatible (dash form).
    rows = parse_wikipedia_nasdaq100(WIKI_HTML)
    assert ("BRK-B", "Fake Dotted") in rows


def test_parse_wikipedia_nasdaq100_missing_table_raises():
    with pytest.raises(ValueError, match="components"):
        parse_wikipedia_nasdaq100("<html><body>nope</body></html>")


# ---------------------------------------------------------------------------
# Membership snapshot (append-only jsonl, idempotent per date)
# ---------------------------------------------------------------------------


def test_membership_snapshot_appends_and_reads_back(tmp_path):
    path = tmp_path / "kosdaq150_membership.jsonl"
    append_membership_snapshot(path, "2026-07-27", ["247540", "086520"])
    append_membership_snapshot(path, "2026-07-28", ["247540"])
    snaps = read_membership_snapshots(path)
    assert snaps == [
        {"date": "2026-07-27", "symbols": ["247540", "086520"]},
        {"date": "2026-07-28", "symbols": ["247540"]},
    ]


def test_membership_snapshot_is_idempotent_per_date(tmp_path):
    path = tmp_path / "m.jsonl"
    append_membership_snapshot(path, "2026-07-27", ["247540"])
    append_membership_snapshot(path, "2026-07-27", ["999999"])  # same date: no-op
    snaps = read_membership_snapshots(path)
    assert snaps == [{"date": "2026-07-27", "symbols": ["247540"]}]


def test_membership_snapshot_rejects_out_of_order_date(tmp_path):
    path = tmp_path / "m.jsonl"
    append_membership_snapshot(path, "2026-07-27", ["247540"])
    with pytest.raises(ValueError, match="2026-07-26"):
        append_membership_snapshot(path, "2026-07-26", ["247540"])


def test_membership_snapshot_rejects_empty_symbols(tmp_path):
    path = tmp_path / "m.jsonl"
    with pytest.raises(ValueError, match="empty"):
        append_membership_snapshot(path, "2026-07-27", [])


def test_membership_file_is_valid_jsonl(tmp_path):
    path = tmp_path / "m.jsonl"
    append_membership_snapshot(path, "2026-07-27", ["247540"])
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec == {"date": "2026-07-27", "symbols": ["247540"]}
