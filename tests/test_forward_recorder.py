# tests/test_forward_recorder.py
"""Tests for the daily forward recorder — RESEARCH ONLY, no network.

The append logic (membership log idempotency + finalized-bar append-only merge)
is pure and fully tested here; the yfinance fetch is injected as a fake.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timezone

from trader.core.events import BarEvent, Market, Symbol
from trader.data.forward_recorder import (
    append_raw_bars,
    append_universe_log,
    record_forward,
    source_symbol,
)
from trader.data.storage import load_bars


def _bar(ticker: str, d: str, market: Market = Market.NASDAQ, close: float = 100.0) -> BarEvent:
    ccy = "KRW" if market == Market.KOSPI else "USD"
    sym = Symbol(ticker, market, ccy)
    ts = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return BarEvent(sym, ts, close, close + 1, close - 1, close, 1_000)


# ---------------------------------------------------------------------------
# source_symbol mapping
# ---------------------------------------------------------------------------

def test_source_symbol_mapping():
    assert source_symbol("AAPL", "NASDAQ") == "AAPL"
    assert source_symbol("005930", "KOSPI") == "005930.KS"


# ---------------------------------------------------------------------------
# Universe membership log
# ---------------------------------------------------------------------------

class TestUniverseLog:
    def setup_method(self):
        self.log = os.path.join(tempfile.mkdtemp(), "_universe_log.jsonl")

    def test_appends_record_with_fields(self):
        syms = [("AAPL", "NASDAQ"), ("005930", "KOSPI")]
        assert append_universe_log(syms, "2026-06-24", log_path=self.log) is True

        lines = open(self.log).read().strip().splitlines()
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["as_of_date"] == "2026-06-24"
        assert rec["n"] == 2
        kr = [s for s in rec["symbols"] if s["market"] == "KOSPI"][0]
        assert kr["currency"] == "KRW"
        assert kr["source_symbol"] == "005930.KS"

    def test_idempotent_same_date(self):
        syms = [("AAPL", "NASDAQ")]
        assert append_universe_log(syms, "2026-06-24", log_path=self.log) is True
        assert append_universe_log(syms, "2026-06-24", log_path=self.log) is False  # no dup
        assert len(open(self.log).read().strip().splitlines()) == 1

    def test_different_dates_both_logged(self):
        append_universe_log([("AAPL", "NASDAQ")], "2026-06-24", log_path=self.log)
        append_universe_log([("AAPL", "NASDAQ")], "2026-06-25", log_path=self.log)
        assert len(open(self.log).read().strip().splitlines()) == 2


# ---------------------------------------------------------------------------
# append_raw_bars — finalized-bar rule, append-only, dedupe
# ---------------------------------------------------------------------------

class TestAppendRawBars:
    def test_excludes_today_and_future(self):
        existing: list[BarEvent] = []
        fetched = [_bar("X", "2026-06-22"), _bar("X", "2026-06-23"), _bar("X", "2026-06-24")]
        out = append_raw_bars(existing, fetched, today=date(2026, 6, 24))
        dates = [b.ts.date().isoformat() for b in out]
        assert dates == ["2026-06-22", "2026-06-23"]  # 06-24 (today) excluded

    def test_append_only_after_existing_max(self):
        existing = [_bar("X", "2026-06-20"), _bar("X", "2026-06-21")]
        fetched = [_bar("X", d) for d in
                   ("2026-06-19", "2026-06-20", "2026-06-21", "2026-06-22", "2026-06-23")]
        out = append_raw_bars(existing, fetched, today=date(2026, 6, 24))
        dates = [b.ts.date().isoformat() for b in out]
        # keeps existing, drops <= max (06-19/20/21), appends 06-22/23 (< today)
        assert dates == ["2026-06-20", "2026-06-21", "2026-06-22", "2026-06-23"]

    def test_dedupe_no_duplicate_dates(self):
        existing = [_bar("X", "2026-06-20")]
        fetched = [_bar("X", "2026-06-21"), _bar("X", "2026-06-21")]  # dup in fetch
        out = append_raw_bars(existing, fetched, today=date(2026, 6, 24))
        dates = [b.ts.date().isoformat() for b in out]
        assert dates == ["2026-06-20", "2026-06-21"]

    def test_empty_existing(self):
        out = append_raw_bars([], [_bar("X", "2026-06-20")], today=date(2026, 6, 24))
        assert len(out) == 1


# ---------------------------------------------------------------------------
# record_forward orchestrator — with a fake fetcher (no network)
# ---------------------------------------------------------------------------

class TestRecordForward:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()
        self.fwd = os.path.join(self.tmp, "forward_data")
        self.log = os.path.join(self.tmp, "_universe_log.jsonl")

    def _fetcher(self, calls: list | None = None):
        def f(ticker, market):
            if calls is not None:
                calls.append((ticker, market))
            return [_bar(ticker, d, Market(market.upper())) for d in
                    ("2026-06-22", "2026-06-23", "2026-06-24")]  # 24 is "today"
        return f

    def test_records_bars_and_membership(self):
        uni = [("AAPL", "NASDAQ"), ("005930", "KOSPI")]
        summary = record_forward(
            "2026-06-24", date(2026, 6, 24), uni,
            fetch_fn=self._fetcher(), forward_dir=self.fwd, log_path=self.log,
        )
        assert summary["membership_logged"] is True
        assert summary["symbols_updated"] == 2
        assert summary["bars_appended"] == 4   # 2 finalized bars x 2 symbols
        assert summary["errors"] == 0

        # parquet written with only finalized bars (no 06-24)
        bars = load_bars(os.path.join(self.fwd, "NASDAQ_AAPL.parquet"))
        assert [b.ts.date().isoformat() for b in bars] == ["2026-06-22", "2026-06-23"]

    def test_second_run_same_day_is_noop(self):
        uni = [("AAPL", "NASDAQ")]
        record_forward("2026-06-24", date(2026, 6, 24), uni,
                       fetch_fn=self._fetcher(), forward_dir=self.fwd, log_path=self.log)
        summary2 = record_forward("2026-06-24", date(2026, 6, 24), uni,
                                  fetch_fn=self._fetcher(), forward_dir=self.fwd, log_path=self.log)
        assert summary2["membership_logged"] is False   # already logged
        assert summary2["bars_appended"] == 0            # nothing new before today

    def test_fetch_error_counted_not_fatal(self):
        def bad_fetch(ticker, market):
            if ticker == "BAD":
                raise RuntimeError("boom")
            return [_bar(ticker, "2026-06-22")]
        uni = [("AAPL", "NASDAQ"), ("BAD", "NASDAQ")]
        summary = record_forward("2026-06-24", date(2026, 6, 24), uni,
                                 fetch_fn=bad_fetch, forward_dir=self.fwd, log_path=self.log)
        assert summary["errors"] == 1
        assert summary["symbols_updated"] == 1   # AAPL still recorded
