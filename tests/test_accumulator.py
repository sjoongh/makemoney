# tests/test_accumulator.py
"""Tests for trader/data/accumulator.py — NO network, sleep injected as no-op."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import pytest

from trader.core.events import BarEvent, Market, Symbol
from trader.data.accumulator import DataAccumulator, _COOLDOWN_SECS, _STALE_DAYS, _key, provider_for


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

def _bar(ticker: str = "AAPL", market: str = "NASDAQ") -> BarEvent:
    sym = Symbol(ticker, Market(market), "USD" if market == "NASDAQ" else "KRW")
    ts = datetime(2024, 1, 2, tzinfo=timezone.utc)
    return BarEvent(sym, ts, 100.0, 110.0, 90.0, 105.0, 1000)


class FakeProvider:
    """Configurable fake; counts calls, can raise on demand."""

    def __init__(self, bars_per_call: int = 3, raises: dict[str, Exception] | None = None):
        self._bars_per_call = bars_per_call
        self._raises = raises or {}  # key → exception to raise
        self.calls: list[tuple[str, str]] = []  # (ticker, market) pairs called

    def daily_history(self, ticker: str, market: str, *, refresh: bool = False) -> list[BarEvent]:
        self.calls.append((ticker, market))
        key = f"{market}|{ticker}"
        if key in self._raises:
            raise self._raises[key]
        return [_bar(ticker, market) for _ in range(self._bars_per_call)]


class SleepCounter:
    """Records how many times it was called and with what durations."""

    def __init__(self):
        self.calls: list[float] = []

    def __call__(self, secs: float) -> None:
        self.calls.append(secs)


def _acc(
    provider,
    universe_list,
    tmp_path,
    per_run=25,
    sleep=None,
    sleep_secs=0.0,
    now=None,
):
    manifest = str(tmp_path / "_manifest.json")
    sc = sleep if sleep is not None else SleepCounter()
    return DataAccumulator(
        provider=provider,
        universe_list=universe_list,
        manifest_path=manifest,
        per_run=per_run,
        sleep=sc,
        sleep_secs=sleep_secs,
        now=now or time.time,
    ), manifest


# ---------------------------------------------------------------------------
# select_next tests
# ---------------------------------------------------------------------------

class TestSelectNext:
    def test_pending_first(self, tmp_path):
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ")]
        prov = FakeProvider()
        acc, manifest = _acc(prov, uni, tmp_path)

        selected = acc.select_next()
        assert ("AAPL", "NASDAQ") in selected
        assert ("MSFT", "NASDAQ") in selected

    def test_skips_active_cooldown(self, tmp_path):
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ")]
        prov = FakeProvider()
        acc, manifest_path = _acc(prov, uni, tmp_path)

        # Write manifest with AAPL in future cooldown
        future = time.time() + 9999
        data = {
            "NASDAQ|AAPL": {
                "status": "cooldown",
                "last_success": None,
                "first_date": None,
                "last_date": None,
                "error_count": 0,
                "last_error": None,
                "cooldown_until": future,
            }
        }
        with open(manifest_path, "w") as f:
            json.dump(data, f)

        selected = acc.select_next()
        tickers = [t for t, _ in selected]
        assert "AAPL" not in tickers
        assert "MSFT" in tickers

    def test_picks_stale_ok(self, tmp_path):
        uni = [("AAPL", "NASDAQ")]
        prov = FakeProvider()
        acc, manifest_path = _acc(prov, uni, tmp_path)

        # Write manifest with AAPL ok but last_success very old
        old_ts = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        data = {
            "NASDAQ|AAPL": {
                "status": "ok",
                "last_success": old_ts,
                "first_date": "2019-01-01",
                "last_date": "2020-01-01",
                "error_count": 0,
                "last_error": None,
                "cooldown_until": None,
            }
        }
        with open(manifest_path, "w") as f:
            json.dump(data, f)

        selected = acc.select_next()
        assert ("AAPL", "NASDAQ") in selected

    def test_skips_fresh_ok(self, tmp_path):
        uni = [("AAPL", "NASDAQ")]
        prov = FakeProvider()
        acc, manifest_path = _acc(prov, uni, tmp_path)

        # last_success = now (fresh)
        now_ts = datetime.now(tz=timezone.utc).isoformat()
        data = {
            "NASDAQ|AAPL": {
                "status": "ok",
                "last_success": now_ts,
                "first_date": "2023-01-01",
                "last_date": "2024-01-02",
                "error_count": 0,
                "last_error": None,
                "cooldown_until": None,
            }
        }
        with open(manifest_path, "w") as f:
            json.dump(data, f)

        selected = acc.select_next()
        assert ("AAPL", "NASDAQ") not in selected

    def test_per_run_limit(self, tmp_path):
        uni = [(f"SYM{i}", "NASDAQ") for i in range(10)]
        prov = FakeProvider()
        acc, _ = _acc(prov, uni, tmp_path, per_run=3)
        selected = acc.select_next()
        assert len(selected) <= 3


# ---------------------------------------------------------------------------
# run_once success path
# ---------------------------------------------------------------------------

class TestRunOnceSuccess:
    def test_success_updates_manifest_to_ok(self, tmp_path):
        uni = [("AAPL", "NASDAQ")]
        prov = FakeProvider()
        sleep = SleepCounter()
        acc, manifest_path = _acc(prov, uni, tmp_path, sleep=sleep)

        summary = acc.run_once()

        assert summary["fetched"] == 1
        assert summary["cooled"] == 0
        assert summary["errored"] == 0

        with open(manifest_path) as f:
            m = json.load(f)

        entry = m["NASDAQ|AAPL"]
        assert entry["status"] == "ok"
        assert entry["last_success"] is not None
        assert entry["first_date"] is not None
        assert entry["last_date"] is not None

    def test_sleep_called_between_fetches(self, tmp_path):
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ"), ("GOOG", "NASDAQ")]
        prov = FakeProvider()
        sleep = SleepCounter()
        acc, _ = _acc(prov, uni, tmp_path, per_run=3, sleep=sleep, sleep_secs=7.0)

        acc.run_once()

        # Sleep is called between fetches: N-1 times for N symbols
        assert len(sleep.calls) == 2
        assert all(s == 7.0 for s in sleep.calls)

    def test_no_sleep_before_first_fetch(self, tmp_path):
        uni = [("AAPL", "NASDAQ")]
        prov = FakeProvider()
        sleep = SleepCounter()
        acc, _ = _acc(prov, uni, tmp_path, sleep=sleep, sleep_secs=5.0)

        acc.run_once()

        assert len(sleep.calls) == 0  # only 1 symbol → no inter-symbol sleep


# ---------------------------------------------------------------------------
# run_once 429 / cooldown path
# ---------------------------------------------------------------------------

class TestRunOnceCooldown:
    def test_429_sets_cooldown_and_stops(self, tmp_path):
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ"), ("GOOG", "NASDAQ")]
        exc_429 = RuntimeError("[RESEARCH] Yahoo rate-limited (429) for AAPL.")
        prov = FakeProvider(raises={"NASDAQ|AAPL": exc_429})
        sleep = SleepCounter()
        acc, manifest_path = _acc(prov, uni, tmp_path, per_run=3, sleep=sleep)

        summary = acc.run_once()

        # Should have stopped after the 429 — only AAPL was called
        assert summary["cooled"] == 1
        assert summary["fetched"] == 0
        assert len(prov.calls) == 1
        assert prov.calls[0] == ("AAPL", "NASDAQ")

        with open(manifest_path) as f:
            m = json.load(f)

        entry = m["NASDAQ|AAPL"]
        assert entry["status"] == "cooldown"
        assert entry["cooldown_until"] is not None
        assert entry["cooldown_until"] > time.time()

        # MSFT and GOOG should still be absent (never attempted)
        assert "NASDAQ|MSFT" not in m
        assert "NASDAQ|GOOG" not in m

    def test_429_in_middle_stops_further_fetches(self, tmp_path):
        """First symbol succeeds, second hits 429 — third must NOT be called."""
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ"), ("GOOG", "NASDAQ")]
        exc_429 = RuntimeError("429 rate-limit")
        prov = FakeProvider(raises={"NASDAQ|MSFT": exc_429})
        sleep = SleepCounter()
        acc, _ = _acc(prov, uni, tmp_path, per_run=3, sleep=sleep)

        summary = acc.run_once()

        assert summary["fetched"] == 1   # AAPL succeeded
        assert summary["cooled"] == 1    # MSFT hit 429
        called_tickers = [t for t, _ in prov.calls]
        assert "GOOG" not in called_tickers  # must NOT be called


# ---------------------------------------------------------------------------
# run_once non-429 error path
# ---------------------------------------------------------------------------

class TestRunOnceError:
    def test_non_429_error_increments_error_count(self, tmp_path):
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ")]
        exc = RuntimeError("Malformed response")
        prov = FakeProvider(raises={"NASDAQ|AAPL": exc})
        sleep = SleepCounter()
        acc, manifest_path = _acc(prov, uni, tmp_path, per_run=2, sleep=sleep)

        summary = acc.run_once()

        assert summary["errored"] == 1
        assert summary["fetched"] == 1   # MSFT should still be fetched

        with open(manifest_path) as f:
            m = json.load(f)

        aapl = m["NASDAQ|AAPL"]
        assert aapl["status"] == "error"
        assert aapl["error_count"] == 1

    def test_non_429_does_not_halt_run(self, tmp_path):
        """A non-429 error should NOT stop remaining symbols from being fetched."""
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ"), ("GOOG", "NASDAQ")]
        exc = RuntimeError("Some other error")
        prov = FakeProvider(raises={"NASDAQ|AAPL": exc})
        sleep = SleepCounter()
        acc, _ = _acc(prov, uni, tmp_path, per_run=3, sleep=sleep)

        acc.run_once()

        called = [t for t, _ in prov.calls]
        assert "MSFT" in called
        assert "GOOG" in called


# ---------------------------------------------------------------------------
# Resumability
# ---------------------------------------------------------------------------

class TestResumability:
    def test_second_run_fetches_remaining(self, tmp_path):
        """After run 1 with per_run=1, run 2 should pick remaining pending."""
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ")]
        prov = FakeProvider()
        sleep = SleepCounter()

        # Run 1 — per_run=1, fetches only one symbol
        acc, manifest_path = _acc(prov, uni, tmp_path, per_run=1, sleep=sleep)
        s1 = acc.run_once()
        assert s1["fetched"] == 1

        # Run 2 — new DataAccumulator instance, same manifest on disk
        acc2, _ = _acc(prov, uni, tmp_path, per_run=1, sleep=sleep)
        s2 = acc2.run_once()
        assert s2["fetched"] == 1

        # Both symbols should now be ok
        with open(manifest_path) as f:
            m = json.load(f)
        assert m["NASDAQ|AAPL"]["status"] == "ok"
        assert m["NASDAQ|MSFT"]["status"] == "ok"

    def test_manifest_persists_across_instances(self, tmp_path):
        """Manifest written by one instance is read correctly by another."""
        uni = [("AAPL", "NASDAQ")]
        prov = FakeProvider()
        acc1, manifest_path = _acc(prov, uni, tmp_path)
        acc1.run_once()

        # New instance — reads same manifest file
        prov2 = FakeProvider()
        acc2, _ = _acc(prov2, uni, tmp_path)
        selected = acc2.select_next()
        # AAPL was just fetched (fresh) — should not be selected again
        assert ("AAPL", "NASDAQ") not in selected


# ---------------------------------------------------------------------------
# Progress helper
# ---------------------------------------------------------------------------

class TestProgress:
    def test_progress_counts(self, tmp_path):
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ")]
        prov = FakeProvider()
        acc, _ = _acc(prov, uni, tmp_path, per_run=1)

        prog_before = acc.progress()
        assert prog_before["total"] == 2
        assert prog_before["pending"] == 2
        assert prog_before["done"] == 0

        acc.run_once()

        prog_after = acc.progress()
        assert prog_after["done"] == 1
        assert prog_after["pending"] == 1


# ---------------------------------------------------------------------------
# provider_for mapping
# ---------------------------------------------------------------------------

class TestProviderFor:
    def test_nasdaq_maps_to_yahoo(self):
        assert provider_for("NASDAQ") == "yahoo"

    def test_nasdaq_case_insensitive(self):
        assert provider_for("nasdaq") == "yahoo"

    def test_kospi_maps_to_naver(self):
        assert provider_for("KOSPI") == "naver"

    def test_kospi_case_insensitive(self):
        assert provider_for("kospi") == "naver"

    def test_unknown_market_returns_yahoo(self):
        # Fallback matches research_provider behaviour (else → Yahoo path)
        assert provider_for("NYSE") == "yahoo"


# ---------------------------------------------------------------------------
# Per-provider cooldown — Yahoo 429 must NOT block Naver (KR) symbols
# ---------------------------------------------------------------------------

class FakeProviderMixed:
    """Raises 429 for NASDAQ symbols only; KOSPI always succeeds."""

    def __init__(self, yahoo_429_tickers: set[str] | None = None, bars_per_call: int = 2):
        self._yahoo_429 = yahoo_429_tickers or set()
        self._bars_per_call = bars_per_call
        self.calls: list[tuple[str, str]] = []

    def daily_history(self, ticker: str, market: str, *, refresh: bool = False) -> list[BarEvent]:
        self.calls.append((ticker, market))
        if market.upper() == "NASDAQ" and ticker in self._yahoo_429:
            raise RuntimeError(f"[RESEARCH] Yahoo rate-limited (429) for {ticker}.")
        return [_bar(ticker, market) for _ in range(self._bars_per_call)]


class TestPerProviderCooldown:
    def test_yahoo_429_does_not_block_naver(self, tmp_path):
        """KEY REGRESSION: Yahoo 429 must not prevent KR/Naver symbols from being fetched."""
        uni = [
            ("AAPL", "NASDAQ"),
            ("MSFT", "NASDAQ"),
            ("005930", "KOSPI"),
            ("000660", "KOSPI"),
        ]
        # All NASDAQ symbols will 429; KOSPI symbols should still succeed
        prov = FakeProviderMixed(yahoo_429_tickers={"AAPL", "MSFT"})
        acc, manifest_path = _acc(prov, uni, tmp_path, per_run=10)

        summary = acc.run_once()

        # KOSPI symbols must have been fetched
        called_kospi = [(t, m) for t, m in prov.calls if m == "KOSPI"]
        assert ("005930", "KOSPI") in called_kospi
        assert ("000660", "KOSPI") in called_kospi

        # Summary: 2 cooled (yahoo), 2 fetched (naver)
        assert summary["cooled"] >= 1
        assert summary["fetched"] == 2

        # Manifest: KOSPI symbols ok, NASDAQ symbols in cooldown
        with open(manifest_path) as f:
            m = json.load(f)

        assert m["KOSPI|005930"]["status"] == "ok"
        assert m["KOSPI|000660"]["status"] == "ok"
        assert m["NASDAQ|AAPL"]["status"] == "cooldown"

    def test_yahoo_429_stops_further_yahoo_fetches(self, tmp_path):
        """After Yahoo 429, no more Yahoo (NASDAQ) symbols are attempted that run."""
        uni = [
            ("AAPL", "NASDAQ"),
            ("MSFT", "NASDAQ"),
            ("GOOG", "NASDAQ"),
            ("005930", "KOSPI"),
        ]
        prov = FakeProviderMixed(yahoo_429_tickers={"AAPL"})
        acc, _ = _acc(prov, uni, tmp_path, per_run=10)

        acc.run_once()

        called_nasdaq = [t for t, m in prov.calls if m == "NASDAQ"]
        # AAPL hit 429 → MSFT and GOOG must NOT be called
        assert "MSFT" not in called_nasdaq
        assert "GOOG" not in called_nasdaq
        # But KOSPI should still have been called
        assert ("005930", "KOSPI") in prov.calls

    def test_naver_429_stops_naver_but_not_yahoo(self, tmp_path):
        """Symmetric: a Naver 429 should cool Naver but leave Yahoo running."""
        uni = [
            ("AAPL", "NASDAQ"),
            ("005930", "KOSPI"),
            ("000660", "KOSPI"),
        ]
        exc_429 = RuntimeError("[RESEARCH] Naver rate-limited (429) for 005930.")
        prov = FakeProvider(raises={"KOSPI|005930": exc_429})
        acc, _ = _acc(prov, uni, tmp_path, per_run=10)

        acc.run_once()

        called = prov.calls
        # Yahoo (AAPL) must still have been called
        assert ("AAPL", "NASDAQ") in called
        # 000660 (also naver) must NOT be called after the 005930 429
        assert ("000660", "KOSPI") not in called

    def test_cooled_provider_set_is_per_run(self, tmp_path):
        """Cooled provider set resets between run_once() calls."""
        uni = [
            ("AAPL", "NASDAQ"),
            ("MSFT", "NASDAQ"),
        ]
        exc_429 = RuntimeError("[RESEARCH] Yahoo rate-limited (429) for AAPL.")
        prov = FakeProvider(raises={"NASDAQ|AAPL": exc_429})
        acc, manifest_path = _acc(prov, uni, tmp_path, per_run=10)

        # Run 1: AAPL 429 → MSFT skipped (same provider)
        s1 = acc.run_once()
        assert s1["cooled"] == 1
        assert s1["fetched"] == 0

        # Remove AAPL from raises so run 2 succeeds for AAPL
        prov._raises = {}

        # Run 2: cooldown_until from manifest means AAPL still skipped by select_next,
        # but MSFT (never tried, still pending) should now be fetched
        s2 = acc.run_once()
        assert s2["fetched"] >= 1
        called_run2 = prov.calls[1:]  # calls after run 1
        assert any(t == "MSFT" for t, _ in called_run2)


# ---------------------------------------------------------------------------
# Provider-interleaved selection — KR(Naver) must not be starved by US(Yahoo)
# ---------------------------------------------------------------------------

class TestSelectNextInterleaved:
    def test_batch_contains_naver_symbols(self, tmp_path):
        """KEY REGRESSION: with many US then few KR symbols all pending,
        select_next must include KR/Naver symbols (not be all-Yahoo)."""
        # 10 US symbols followed by 3 KR symbols — all pending
        us_symbols = [(f"US{i:02d}", "NASDAQ") for i in range(10)]
        kr_symbols = [("005930", "KOSPI"), ("000660", "KOSPI"), ("035420", "KOSPI")]
        uni = us_symbols + kr_symbols
        prov = FakeProvider()
        acc, _ = _acc(prov, uni, tmp_path, per_run=6)

        selected = acc.select_next()

        providers_selected = {provider_for(mkt) for _, mkt in selected}
        assert "naver" in providers_selected, (
            "select_next returned all-Yahoo batch — KR symbols starved"
        )

    def test_round_robin_two_providers_splits_evenly(self, tmp_path):
        """per_run=4, 2 providers with >=2 symbols each → ~2 from each."""
        uni = [
            ("US00", "NASDAQ"), ("US01", "NASDAQ"), ("US02", "NASDAQ"),
            ("005930", "KOSPI"), ("000660", "KOSPI"), ("035420", "KOSPI"),
        ]
        prov = FakeProvider()
        acc, _ = _acc(prov, uni, tmp_path, per_run=4)

        selected = acc.select_next()

        assert len(selected) == 4
        yahoo_count = sum(1 for _, m in selected if provider_for(m) == "yahoo")
        naver_count = sum(1 for _, m in selected if provider_for(m) == "naver")
        # Round-robin: 2 from each provider
        assert yahoo_count == 2
        assert naver_count == 2

    def test_single_provider_no_error(self, tmp_path):
        """When only one provider has eligible symbols, batch is just that provider."""
        uni = [("AAPL", "NASDAQ"), ("MSFT", "NASDAQ"), ("GOOG", "NASDAQ")]
        prov = FakeProvider()
        acc, _ = _acc(prov, uni, tmp_path, per_run=5)

        selected = acc.select_next()

        assert len(selected) == 3
        assert all(provider_for(m) == "yahoo" for _, m in selected)

    def test_run_once_yahoo_429_naver_fetched(self, tmp_path):
        """Full run_once sim: all yahoo 429 → naver symbols still fetched (manifest ok)."""
        us_symbols = [(f"US{i:02d}", "NASDAQ") for i in range(5)]
        kr_symbols = [("005930", "KOSPI"), ("000660", "KOSPI")]
        uni = us_symbols + kr_symbols

        # All NASDAQ raise 429; KOSPI always succeeds
        prov = FakeProviderMixed(yahoo_429_tickers={t for t, _ in us_symbols})
        acc, manifest_path = _acc(prov, uni, tmp_path, per_run=8)

        summary = acc.run_once()

        # KR symbols must be in the batch AND fetched
        called_markets = [m for _, m in prov.calls]
        assert "KOSPI" in called_markets, "KOSPI symbols never entered the batch"
        assert summary["fetched"] == 2  # only naver succeeded
        assert summary["cooled"] >= 1   # at least one yahoo was cooled

        with open(manifest_path) as f:
            m = json.load(f)
        assert m["KOSPI|005930"]["status"] == "ok"
        assert m["KOSPI|000660"]["status"] == "ok"

    def test_more_yahoo_than_naver_fills_remainder_from_yahoo(self, tmp_path):
        """Round-robin exhausts naver early; remaining slots filled with yahoo."""
        # 6 yahoo, 2 naver, per_run=6
        uni = [(f"US{i:02d}", "NASDAQ") for i in range(6)] + [
            ("005930", "KOSPI"), ("000660", "KOSPI")
        ]
        prov = FakeProvider()
        acc, _ = _acc(prov, uni, tmp_path, per_run=6)

        selected = acc.select_next()

        assert len(selected) == 6
        naver_count = sum(1 for _, m in selected if provider_for(m) == "naver")
        yahoo_count = sum(1 for _, m in selected if provider_for(m) == "yahoo")
        # All 2 naver symbols included; remaining 4 slots filled from yahoo
        assert naver_count == 2
        assert yahoo_count == 4
