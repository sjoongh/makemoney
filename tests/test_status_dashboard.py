# tests/test_status_dashboard.py
"""Tests for the unified status dashboard — pure gather rollup + renderers."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from trader.app import status_dashboard as sd


class FakeKis:
    account = "50193330"

    def __init__(self, snap, fx=1550.0):
        self._snap = snap
        self._fx = fx

    def account_snapshot(self):
        return self._snap

    def usd_krw_rate(self, default=-1.0):
        return self._fx


def _snap():
    return {
        "cash_krw": 34_000_000.0,
        "nass_krw": 99_600_000.0,
        "ovr_purchase_krw": 50_000_000.0,
        "positions": {("KOSPI", "069500"): 122, ("NASDAQ", "SPY"): 43},
        "marks": {("KOSPI", "069500"): 131_000.0, ("NASDAQ", "SPY"): 745.0},
    }


def _write(tmp_path, hb=None, manifest=None, track=None):
    hbp = tmp_path / ".heartbeat.json"
    hbp.write_text(json.dumps(hb or {}))
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(manifest or {}))
    tp = tmp_path / "track.jsonl"
    tp.write_text("\n".join(json.dumps(r) for r in (track or [])))
    return str(hbp), str(mp), str(tp)


NOW = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)


def test_gather_healthy_all_fresh(tmp_path):
    hb = {"accumulator": "2026-07-03T06:00:00+00:00",
          "forward_record": "2026-07-03T05:00:00+00:00",
          "beta_kis_kr": "2026-07-03T01:00:00+00:00",
          "beta_kis_us": "2026-07-02T14:00:00+00:00"}
    manifest = {"NASDAQ|AAPL": {"status": "ok", "last_date": "2026-07-02"}}
    track = [{"as_of": "2026-07-02T14:35:00+00:00", "equity_krw": 99_000_000.0,
              "market": "US", "side": "SELL", "qty": 21, "etf": "SPY",
              "submitted_odno": "0000044416"}]
    hbp, mp, tp = _write(tmp_path, hb, manifest, track)
    s = sd.gather_status(kis=FakeKis(_snap()), heartbeat_path=hbp, manifest_path=mp,
                         track_path=tp, now=NOW, with_benchmarks=False)
    assert s["healthy"] is True
    assert s["problems"] == []
    # equity = 99.6M - 50M + 43*745*1550
    exp = 99_600_000 - 50_000_000 + 43 * 745 * 1550
    assert abs(s["sections"]["account"]["equity_krw"] - exp) < 1
    assert len(s["sections"]["account"]["positions"]) == 2
    assert s["sections"]["fills"][0]["odno"] == "0000044416"


def test_gather_flags_stale_job(tmp_path):
    hb = {"accumulator": "2026-06-01T06:00:00+00:00"}  # ancient → stale
    hbp, mp, tp = _write(tmp_path, hb, {"X|Y": {"status": "ok", "last_date": "2026-07-02"}}, [])
    s = sd.gather_status(kis=FakeKis(_snap()), heartbeat_path=hbp, manifest_path=mp,
                         track_path=tp, now=NOW, with_benchmarks=False)
    assert s["healthy"] is False
    assert any("STALE" in p for p in s["problems"])


def test_gather_survives_account_error(tmp_path):
    class Broken:
        account = "x"
        def account_snapshot(self):
            raise RuntimeError("KIS down")
        def usd_krw_rate(self, default=-1.0):
            return -1.0
    hbp, mp, tp = _write(tmp_path)
    s = sd.gather_status(kis=Broken(), heartbeat_path=hbp, manifest_path=mp,
                         track_path=tp, now=NOW, with_benchmarks=False)
    # one section failing must not blank the whole thing
    assert "error" in s["sections"]["account"]
    assert "account unreadable" in s["problems"]
    assert "jobs" in s["sections"]


def test_renderers_produce_output(tmp_path):
    hbp, mp, tp = _write(tmp_path, {"accumulator": "2026-07-03T06:00:00+00:00"},
                         {"X|Y": {"status": "ok", "last_date": "2026-07-02"}}, [])
    s = sd.gather_status(kis=FakeKis(_snap()), heartbeat_path=hbp, manifest_path=mp,
                         track_path=tp, now=NOW, with_benchmarks=False)
    term = sd.render_terminal(s)
    assert "MAKEMONEY" in term and "069500" in term
    doc = sd.render_html(s)
    assert doc.startswith("<!doctype html>") and "makemoney" in doc
    assert "069500" in doc


def test_html_escapes_error_text(tmp_path):
    class Evil:
        account = "x"
        def account_snapshot(self):
            raise RuntimeError("<script>alert(1)</script>")
        def usd_krw_rate(self, default=-1.0):
            return -1.0
    hbp, mp, tp = _write(tmp_path)
    s = sd.gather_status(kis=Evil(), heartbeat_path=hbp, manifest_path=mp,
                         track_path=tp, now=NOW, with_benchmarks=False)
    doc = sd.render_html(s)
    assert "<script>alert(1)</script>" not in doc
    assert "&lt;script&gt;" in doc
