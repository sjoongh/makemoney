# tests/test_manifest.py
"""Tests for trader.data.manifest — dataset reproducibility foundation (P0).

Tests:
  - content_hash determinism (same bars → same hash; changed bar → different hash)
  - build_manifest derives symbols/dates/n_bars correctly
  - save/load round-trip (JSON)
  - verify() True on unchanged bars, False on mutated bars
  - save_bars_with_manifest writes both parquet + sidecar; reload matches
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from trader.core.events import BarEvent, Market, Symbol
from trader.data.manifest import (
    DatasetManifest,
    build_manifest,
    content_hash_of,
    current_git_commit,
    load_manifest,
    save_bars_with_manifest,
    save_manifest,
    verify,
)
from trader.data.storage import load_bars


# ---------------------------------------------------------------------------
# Fixtures — minimal reproducible bars
# ---------------------------------------------------------------------------

_SYM_US = Symbol("AAPL", Market.NASDAQ, "USD")
_SYM_KR = Symbol("005930", Market.KOSPI, "KRW")

_T0 = datetime(2023, 1, 3, tzinfo=timezone.utc)


def _make_bars(
    n: int = 5,
    symbol: Symbol = _SYM_US,
    base_close: float = 100.0,
) -> list[BarEvent]:
    """Create *n* ascending daily bars."""
    bars = []
    for i in range(n):
        ts = _T0 + timedelta(days=i)
        c = base_close + i
        bars.append(BarEvent(symbol, ts, c, c + 1, c - 1, c, 1000 + i * 10))
    return bars


_CREATED_TS = "2024-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# 1. content_hash_of — determinism
# ---------------------------------------------------------------------------

class TestContentHashOf:
    def test_same_bars_same_hash(self):
        bars = _make_bars()
        h1 = content_hash_of(bars)
        h2 = content_hash_of(bars)
        assert h1 == h2

    def test_same_bars_different_order_same_hash(self):
        """Hash is order-independent (bars are sorted canonically before hashing)."""
        bars = _make_bars()
        reversed_bars = list(reversed(bars))
        assert content_hash_of(bars) == content_hash_of(reversed_bars)

    def test_changed_close_different_hash(self):
        bars = _make_bars()
        sym = bars[0].symbol
        ts = bars[0].ts
        mutated = BarEvent(sym, ts, bars[0].open, bars[0].high, bars[0].low,
                           bars[0].close + 0.01, bars[0].volume)
        changed = [mutated] + bars[1:]
        assert content_hash_of(bars) != content_hash_of(changed)

    def test_changed_volume_different_hash(self):
        bars = _make_bars()
        b = bars[2]
        mutated = BarEvent(b.symbol, b.ts, b.open, b.high, b.low, b.close, b.volume + 1)
        changed = bars[:2] + [mutated] + bars[3:]
        assert content_hash_of(bars) != content_hash_of(changed)

    def test_extra_bar_different_hash(self):
        bars = _make_bars(5)
        bars_plus = _make_bars(6)
        assert content_hash_of(bars) != content_hash_of(bars_plus)

    def test_empty_bars_returns_stable_hash(self):
        """Empty list should hash deterministically (not raise)."""
        h = content_hash_of([])
        assert isinstance(h, str) and len(h) == 64

    def test_hash_is_64_hex_chars(self):
        bars = _make_bars()
        h = content_hash_of(bars)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_multi_symbol_hash_stable(self):
        bars_us = _make_bars(3, _SYM_US)
        bars_kr = _make_bars(3, _SYM_KR)
        combined = bars_us + bars_kr
        h1 = content_hash_of(combined)
        h2 = content_hash_of(combined)
        assert h1 == h2

    def test_multi_symbol_order_independent(self):
        bars_us = _make_bars(3, _SYM_US)
        bars_kr = _make_bars(3, _SYM_KR)
        assert content_hash_of(bars_us + bars_kr) == content_hash_of(bars_kr + bars_us)


# ---------------------------------------------------------------------------
# 2. build_manifest — derived fields
# ---------------------------------------------------------------------------

class TestBuildManifest:
    def test_n_bars_matches(self):
        bars = _make_bars(7)
        m = build_manifest(bars, dataset_id="test", provider="Yahoo",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        assert m.n_bars == 7

    def test_symbols_derived(self):
        bars = _make_bars(3, _SYM_US) + _make_bars(3, _SYM_KR)
        m = build_manifest(bars, dataset_id="test", provider="Yahoo",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        assert set(m.symbols) == {"AAPL", "005930"}
        assert m.symbols == sorted(m.symbols)  # must be sorted

    def test_start_end_dates(self):
        bars = _make_bars(5)
        m = build_manifest(bars, dataset_id="test", provider="Yahoo",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        assert m.start_date == "2023-01-03"
        assert m.end_date == "2023-01-07"

    def test_content_hash_set(self):
        bars = _make_bars(5)
        m = build_manifest(bars, dataset_id="test", provider="Yahoo",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        assert m.content_hash == content_hash_of(bars)

    def test_metadata_fields(self):
        bars = _make_bars()
        m = build_manifest(bars, dataset_id="MY_DS", provider="Naver",
                           adjustment="raw", created_ts=_CREATED_TS,
                           code_commit="abc123", quality_passed=True)
        assert m.dataset_id == "MY_DS"
        assert m.provider == "Naver"
        assert m.adjustment == "raw"
        assert m.created_ts == _CREATED_TS
        assert m.code_commit == "abc123"
        assert m.quality_passed is True

    def test_optional_fields_default_none(self):
        bars = _make_bars()
        m = build_manifest(bars, dataset_id="X", provider="Y",
                           adjustment="unknown", created_ts=_CREATED_TS)
        assert m.code_commit is None
        assert m.quality_passed is None

    def test_empty_bars_raises(self):
        with pytest.raises(ValueError, match="empty"):
            build_manifest([], dataset_id="X", provider="Y",
                           adjustment="unknown", created_ts=_CREATED_TS)

    def test_manifest_is_frozen(self):
        bars = _make_bars()
        m = build_manifest(bars, dataset_id="X", provider="Y",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        with pytest.raises((AttributeError, TypeError)):
            m.n_bars = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 3. save_manifest / load_manifest — round-trip
# ---------------------------------------------------------------------------

class TestSaveLoadManifest:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def _manifest(self, **overrides) -> DatasetManifest:
        bars = _make_bars()
        kwargs = dict(
            dataset_id="NASDAQ_AAPL",
            provider="Yahoo",
            adjustment="adjusted",
            created_ts=_CREATED_TS,
            code_commit="deadbeef",
            quality_passed=True,
        )
        kwargs.update(overrides)
        return build_manifest(bars, **kwargs)

    def test_round_trip_all_fields(self):
        m = self._manifest()
        path = os.path.join(self.tmp, "manifest.json")
        save_manifest(m, path)
        loaded = load_manifest(path)
        assert loaded == m

    def test_json_file_is_valid_json(self):
        m = self._manifest()
        path = os.path.join(self.tmp, "manifest.json")
        save_manifest(m, path)
        with open(path) as fh:
            data = json.load(fh)
        assert data["dataset_id"] == "NASDAQ_AAPL"
        assert data["n_bars"] == 5

    def test_none_fields_round_trip(self):
        bars = _make_bars()
        m = build_manifest(bars, dataset_id="X", provider="Y",
                           adjustment="unknown", created_ts=_CREATED_TS)
        path = os.path.join(self.tmp, "manifest_none.json")
        save_manifest(m, path)
        loaded = load_manifest(path)
        assert loaded.code_commit is None
        assert loaded.quality_passed is None

    def test_symbols_preserved_as_list(self):
        bars = _make_bars(3, _SYM_US) + _make_bars(3, _SYM_KR)
        m = build_manifest(bars, dataset_id="multi", provider="mixed",
                           adjustment="mixed", created_ts=_CREATED_TS)
        path = os.path.join(self.tmp, "multi.json")
        save_manifest(m, path)
        loaded = load_manifest(path)
        assert isinstance(loaded.symbols, list)
        assert set(loaded.symbols) == {"AAPL", "005930"}


# ---------------------------------------------------------------------------
# 4. verify()
# ---------------------------------------------------------------------------

class TestVerify:
    def test_verify_true_on_same_bars(self):
        bars = _make_bars()
        m = build_manifest(bars, dataset_id="X", provider="Y",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        assert verify(m, bars) is True

    def test_verify_true_on_different_order(self):
        """verify must tolerate out-of-order bars (same canonical content)."""
        bars = _make_bars()
        m = build_manifest(bars, dataset_id="X", provider="Y",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        assert verify(m, list(reversed(bars))) is True

    def test_verify_false_on_mutated_close(self):
        bars = _make_bars()
        m = build_manifest(bars, dataset_id="X", provider="Y",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        b = bars[0]
        mutated = [BarEvent(b.symbol, b.ts, b.open, b.high, b.low,
                            b.close + 1.0, b.volume)] + bars[1:]
        assert verify(m, mutated) is False

    def test_verify_false_on_extra_bar(self):
        bars = _make_bars(5)
        m = build_manifest(bars, dataset_id="X", provider="Y",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        assert verify(m, _make_bars(6)) is False

    def test_verify_false_on_removed_bar(self):
        bars = _make_bars(5)
        m = build_manifest(bars, dataset_id="X", provider="Y",
                           adjustment="adjusted", created_ts=_CREATED_TS)
        assert verify(m, bars[1:]) is False


# ---------------------------------------------------------------------------
# 5. save_bars_with_manifest — writes both parquet + sidecar
# ---------------------------------------------------------------------------

class TestSaveBarsWithManifest:
    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_both_files_created(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        save_bars_with_manifest(
            bars, path,
            provider="Yahoo", adjustment="adjusted", created_ts=_CREATED_TS,
        )
        assert os.path.exists(path)
        assert os.path.exists(path + ".manifest.json")

    def test_parquet_loadable_and_matches(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        save_bars_with_manifest(
            bars, path,
            provider="Yahoo", adjustment="adjusted", created_ts=_CREATED_TS,
        )
        loaded = load_bars(path)
        assert len(loaded) == len(bars)

    def test_sidecar_manifest_reload_matches(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        m1 = save_bars_with_manifest(
            bars, path,
            provider="Yahoo", adjustment="adjusted", created_ts=_CREATED_TS,
            dataset_id="NASDAQ_AAPL",
        )
        m2 = load_manifest(path + ".manifest.json")
        assert m1 == m2

    def test_manifest_content_hash_matches_bars(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        m = save_bars_with_manifest(
            bars, path,
            provider="Yahoo", adjustment="adjusted", created_ts=_CREATED_TS,
        )
        assert m.content_hash == content_hash_of(bars)

    def test_default_dataset_id_from_filename(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        m = save_bars_with_manifest(
            bars, path,
            provider="Yahoo", adjustment="adjusted", created_ts=_CREATED_TS,
        )
        assert m.dataset_id == "NASDAQ_AAPL"

    def test_explicit_dataset_id(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "data.parquet")
        m = save_bars_with_manifest(
            bars, path,
            provider="Yahoo", adjustment="adjusted", created_ts=_CREATED_TS,
            dataset_id="MY_CUSTOM_ID",
        )
        assert m.dataset_id == "MY_CUSTOM_ID"

    def test_verify_passes_after_round_trip(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        m = save_bars_with_manifest(
            bars, path,
            provider="Yahoo", adjustment="adjusted", created_ts=_CREATED_TS,
        )
        loaded_bars = load_bars(path)
        loaded_m = load_manifest(path + ".manifest.json")
        assert verify(loaded_m, loaded_bars) is True

    def test_quality_passed_stored_in_manifest(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "q.parquet")
        m = save_bars_with_manifest(
            bars, path,
            provider="Naver", adjustment="raw", created_ts=_CREATED_TS,
            quality_passed=False,
        )
        loaded = load_manifest(path + ".manifest.json")
        assert loaded.quality_passed is False

    def test_code_commit_stored_in_manifest(self):
        bars = _make_bars()
        path = os.path.join(self.tmp, "c.parquet")
        m = save_bars_with_manifest(
            bars, path,
            provider="Yahoo", adjustment="adjusted", created_ts=_CREATED_TS,
            code_commit="abc123def456",
        )
        loaded = load_manifest(path + ".manifest.json")
        assert loaded.code_commit == "abc123def456"


# ---------------------------------------------------------------------------
# 6. current_git_commit
# ---------------------------------------------------------------------------

class TestCurrentGitCommit:
    def test_returns_string_or_none(self):
        result = current_git_commit()
        assert result is None or isinstance(result, str)

    def test_if_string_is_40_chars(self):
        result = current_git_commit()
        if result is not None:
            assert len(result) == 40
            assert all(c in "0123456789abcdef" for c in result)


# ---------------------------------------------------------------------------
# 7. ResearchDataProvider integration — sidecar written on fetch
# ---------------------------------------------------------------------------

class TestResearchProviderManifestIntegration:
    """Verify that daily_history() now writes sidecar .manifest.json."""

    def setup_method(self):
        self.tmp = tempfile.mkdtemp()

    def test_yahoo_fetch_writes_sidecar(self):
        """Fetching NASDAQ bars must produce both parquet + .manifest.json."""
        import json as _json
        import httpx

        payload = {
            "chart": {
                "result": [{
                    "timestamp": [1672704000, 1672790400, 1672876800],
                    "indicators": {
                        "quote": [{"open": [130.0, 127.0, 128.0],
                                   "high": [133.0, 131.0, 132.0],
                                   "low":  [129.0, 126.0, 127.0],
                                   "close":[131.0, 129.0, 130.0],
                                   "volume":[100_000, 110_000, 105_000]}],
                        "adjclose": [{"adjclose": [130.0, 128.0, 129.0]}],
                    },
                }],
                "error": None,
            }
        }

        def _handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=_json.dumps(payload).encode())

        from trader.data.research_provider import ResearchDataProvider
        client = httpx.Client(transport=httpx.MockTransport(_handler))
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)
        p.daily_history("AAPL", "NASDAQ", refresh=True)

        cache_path = os.path.join(self.tmp, "NASDAQ_AAPL.parquet")
        sidecar = cache_path + ".manifest.json"
        assert os.path.exists(sidecar), "Sidecar .manifest.json must be written"

        m = load_manifest(sidecar)
        assert m.dataset_id == "NASDAQ_AAPL"
        assert m.provider == "Yahoo"
        assert m.adjustment == "adjusted"
        assert m.n_bars == 3
        assert m.quality_passed is not None

    def test_naver_fetch_writes_sidecar(self):
        """Fetching KOSPI bars must produce both parquet + .manifest.json."""
        import httpx

        xml = """<?xml version="1.0" encoding="EUC-KR" ?>
<protocol>
<chartdata symbol="005930" count="3" timeframe="day">
<item data="20230103|130|133|129|131|100000" />
<item data="20230104|127|131|126|129|110000" />
<item data="20230105|128|132|127|130|105000" />
</chartdata>
</protocol>"""

        def _handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=xml.encode("utf-8"))

        from trader.data.research_provider import ResearchDataProvider
        client = httpx.Client(transport=httpx.MockTransport(_handler))
        p = ResearchDataProvider(client=client, cache_dir=self.tmp)
        p.daily_history("005930", "KOSPI", refresh=True)

        cache_path = os.path.join(self.tmp, "KOSPI_005930.parquet")
        sidecar = cache_path + ".manifest.json"
        assert os.path.exists(sidecar), "Sidecar .manifest.json must be written"

        m = load_manifest(sidecar)
        assert m.dataset_id == "KOSPI_005930"
        assert m.provider == "Naver"
        assert m.adjustment == "raw"
        assert m.n_bars == 3
