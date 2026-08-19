# tests/test_edgar_events.py
"""Phase 3 (free-data expansion) — EDGAR 8-K events from the submissions API.

Pure parsing/normalization tests on captured-shape fixtures; no network.
See .omc/specs/deep-interview-free-data-expansion.md.
"""
from __future__ import annotations

import pytest

from trader.data.edgar_events import (
    normalize_edgar_events,
    parse_submissions,
)

# data.sec.gov/submissions/CIK##########.json → filings.recent is columnar.
SUBMISSIONS = {
    "cik": "320193",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "accessionNumber": [
                "0000320193-26-000055",
                "0000320193-26-000042",
                "0000320193-26-000033",
            ],
            "form": ["8-K", "10-Q", "8-K"],
            "acceptanceDateTime": [
                "2026-07-24T16:30:12.000Z",
                "2026-06-30T18:01:00.000Z",
                "2026-05-02T20:15:45.000Z",
            ],
            "filingDate": ["2026-07-24", "2026-06-30", "2026-05-02"],
            "items": ["2.02,9.01", "", "5.02"],
            "primaryDocument": ["ap8k.htm", "ap10q.htm", "ap8k2.htm"],
        }
    },
}


def test_parse_submissions_returns_row_dicts():
    rows = parse_submissions(SUBMISSIONS)
    assert len(rows) == 3
    assert rows[0] == {
        "accession": "0000320193-26-000055",
        "form": "8-K",
        "accepted_ts": "2026-07-24T16:30:12.000Z",
        "filing_date": "2026-07-24",
        "items": "2.02,9.01",
        "primary_doc": "ap8k.htm",
    }


def test_parse_submissions_ragged_columns_raise():
    bad = {"filings": {"recent": {"form": ["8-K"], "accessionNumber": []}}}
    with pytest.raises(ValueError, match="ragged"):
        parse_submissions(bad)


def test_parse_submissions_missing_filings_raise():
    with pytest.raises(ValueError, match="filings"):
        parse_submissions({"cik": "1"})


def test_normalize_keeps_event_forms_and_builds_schema():
    rows = normalize_edgar_events("AAPL", "320193", parse_submissions(SUBMISSIONS))
    assert [r["event_type"] for r in rows] == ["8-K:2.02", "8-K:5.02"]
    r = rows[0]
    assert r["market"] == "NASDAQ"
    assert r["symbol"] == "AAPL"
    assert r["accepted_ts"] == "2026-07-24T16:30:12.000Z"
    assert r["source_id"] == "0000320193-26-000055"
    assert r["title"] == "8-K items 2.02,9.01"
    assert (
        r["url"]
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000055/ap8k.htm"
    )


def test_normalize_event_type_uses_first_item_and_handles_empty_items():
    subs = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000000-26-000001"],
                "form": ["8-K"],
                "acceptanceDateTime": ["2026-01-05T12:00:00.000Z"],
                "filingDate": ["2026-01-05"],
                "items": [""],
                "primaryDocument": ["x.htm"],
            }
        }
    }
    rows = normalize_edgar_events("NVDA", "1045810", parse_submissions(subs))
    assert rows[0]["event_type"] == "8-K"


def test_normalize_includes_6k_for_foreign_private_issuers():
    # FPIs (ASML, PDD, ARM…) never file 8-K; their material-event form is 6-K.
    subs = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000000-26-000003", "0000000000-26-000004"],
                "form": ["6-K", "20-F"],
                "acceptanceDateTime": [
                    "2026-02-01T10:00:00.000Z",
                    "2026-03-01T10:00:00.000Z",
                ],
                "filingDate": ["2026-02-01", "2026-03-01"],
                "items": ["", ""],
                "primaryDocument": ["a.htm", "b.htm"],
            }
        }
    }
    rows = normalize_edgar_events("ASML", "937966", parse_submissions(subs))
    assert [r["event_type"] for r in rows] == ["6-K"]


def test_normalize_rejects_missing_acceptance_ts():
    subs = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000000000-26-000002"],
                "form": ["8-K"],
                "acceptanceDateTime": [""],
                "filingDate": ["2026-01-05"],
                "items": ["2.02"],
                "primaryDocument": ["x.htm"],
            }
        }
    }
    with pytest.raises(ValueError, match="acceptance"):
        normalize_edgar_events("NVDA", "1045810", parse_submissions(subs))
