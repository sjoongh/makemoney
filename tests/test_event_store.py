# tests/test_event_store.py
"""Free-data expansion — event store (parquet + manifest, dedupe/merge).

See .omc/specs/deep-interview-free-data-expansion.md §4.
"""
from __future__ import annotations

import json

import pytest

from trader.data.event_store import load_events, save_events

ROW_A = {
    "market": "NASDAQ", "symbol": "AAPL", "corp": "320193",
    "event_type": "8-K:2.02", "title": "8-K items 2.02,9.01",
    "accepted_ts": "2026-04-30T20:30:41.000Z", "filing_date": "2026-04-30",
    "source_id": "0000320193-26-000011", "url": "https://example/a",
}
ROW_B = {
    "market": "NASDAQ", "symbol": "AAPL", "corp": "320193",
    "event_type": "8-K:5.02", "title": "8-K items 5.02",
    "accepted_ts": "2026-07-24T16:30:12.000Z", "filing_date": "2026-07-24",
    "source_id": "0000320193-26-000055", "url": "https://example/b",
}


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "NASDAQ_events.parquet"
    n = save_events(path, [ROW_B, ROW_A], created_ts="2026-07-27T00:00:00+00:00")
    assert n == 2
    rows = load_events(path)
    # sorted by accepted_ts ascending
    assert [r["source_id"] for r in rows] == [ROW_A["source_id"], ROW_B["source_id"]]


def test_save_merges_with_existing_and_dedupes(tmp_path):
    path = tmp_path / "e.parquet"
    save_events(path, [ROW_A], created_ts="2026-07-27T00:00:00+00:00")
    n = save_events(path, [ROW_A, ROW_B], created_ts="2026-07-28T00:00:00+00:00")
    assert n == 2  # not 3 — ROW_A deduped by source_id
    assert len(load_events(path)) == 2


def test_manifest_written_with_content_hash(tmp_path):
    path = tmp_path / "e.parquet"
    save_events(path, [ROW_A], created_ts="2026-07-27T00:00:00+00:00")
    man = json.loads((tmp_path / "e.parquet.manifest.json").read_text())
    assert man["n_rows"] == 1
    assert len(man["content_hash"]) == 64
    assert man["created_ts"] == "2026-07-27T00:00:00+00:00"


def test_content_hash_is_order_independent(tmp_path):
    p1, p2 = tmp_path / "a.parquet", tmp_path / "b.parquet"
    save_events(p1, [ROW_A, ROW_B], created_ts="2026-07-27T00:00:00+00:00")
    save_events(p2, [ROW_B, ROW_A], created_ts="2026-07-27T00:00:00+00:00")
    h1 = json.loads((tmp_path / "a.parquet.manifest.json").read_text())["content_hash"]
    h2 = json.loads((tmp_path / "b.parquet.manifest.json").read_text())["content_hash"]
    assert h1 == h2


def test_save_rejects_missing_required_field(tmp_path):
    bad = dict(ROW_A)
    del bad["source_id"]
    with pytest.raises(ValueError, match="source_id"):
        save_events(tmp_path / "e.parquet", [bad], created_ts="2026-07-27T00:00:00+00:00")


def test_load_missing_file_returns_empty(tmp_path):
    assert load_events(tmp_path / "nope.parquet") == []


def test_same_filing_under_two_share_classes_keeps_both(tmp_path):
    # GOOG and GOOGL share one CIK → identical accession numbers. The dedupe
    # key must be (symbol, source_id), not source_id alone.
    goog = dict(ROW_A, symbol="GOOG")
    googl = dict(ROW_A, symbol="GOOGL")
    path = tmp_path / "e.parquet"
    n = save_events(path, [goog, googl], created_ts="2026-07-27T00:00:00+00:00")
    assert n == 2
    assert sorted(r["symbol"] for r in load_events(path)) == ["GOOG", "GOOGL"]
