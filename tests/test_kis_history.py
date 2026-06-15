# tests/test_kis_history.py
"""Unit tests for KisClient.daily_bars_history — paginated multi-page fetch.

Uses httpx.MockTransport (no real network). Verifies:
  - NASDAQ: pages stitched, overlap deduped, ascending sorted, stops at lookback/max_pages
  - KOSPI: window-backward pages stitched, deduped, ascending sorted
  - Stopping conditions: max_pages, empty page, lookback window exhausted
"""
from __future__ import annotations

import httpx
import pytest

from trader.core.events import BarEvent, Market
from trader.execution.kis_client import KisClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kis(handler, tmp_path, min_interval: float = 0) -> KisClient:
    c = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://mock")
    return KisClient(
        c, "k", "s", "50193330",
        paper=True, min_interval=min_interval,
        token_cache_path=str(tmp_path / "tok.json"),
    )


def _token_resp():
    return httpx.Response(200, json={"access_token": "T", "expires_in": 86400})


def _overseas_page(rows):
    return httpx.Response(200, json={"rt_cd": "0", "msg1": "ok", "output2": rows})


def _domestic_page(rows):
    return httpx.Response(200, json={"rt_cd": "0", "msg1": "ok", "output2": rows})


def _make_overseas_row(yyyymmdd: str, close: str = "10.0") -> dict:
    return {
        "xymd": yyyymmdd,
        "open": "10",
        "high": "11",
        "low": "9",
        "clos": close,
        "tvol": "100",
    }


def _make_domestic_row(yyyymmdd: str, close: str = "50000") -> dict:
    return {
        "stck_bsop_date": yyyymmdd,
        "stck_oprc": "50000",
        "stck_hgpr": "51000",
        "stck_lwpr": "49000",
        "stck_clpr": close,
        "acml_vol": "1000",
    }


# ---------------------------------------------------------------------------
# NASDAQ pagination tests
# ---------------------------------------------------------------------------

class TestNasdaqPagination:
    """NASDAQ: BYMD anchor pagination."""

    def test_two_pages_stitched_ascending_deduped(self, tmp_path):
        """Two non-overlapping pages → 200 bars, ascending, no dups."""

        # Page 1: 20260101–20260110 (10 bars, most recent)
        page1_rows = [_make_overseas_row(f"2026010{i+1}" if i < 9 else "20260110")
                      for i in range(10)]
        # page1 dates: 20260101..20260110
        page1_rows = [_make_overseas_row("202601%02d" % d) for d in range(1, 11)]

        # Page 2: 20250901–20250910 (10 bars, older)
        page2_rows = [_make_overseas_row("202509%02d" % d) for d in range(1, 11)]

        call_count = [0]

        def handler(req):
            p = str(req.url.path)
            if p.endswith("/oauth2/tokenP"):
                return _token_resp()
            if "overseas-price" in p:
                n = call_count[0]
                call_count[0] += 1
                if n == 0:
                    return _overseas_page(page1_rows)
                else:
                    return _overseas_page(page2_rows)
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        # lookback = 500 days so both pages are within window; max_pages=5
        bars = kis.daily_bars_history("AAPL", "NASDAQ", "USD",
                                      lookback_days=500, max_pages=5)

        dates = [b.ts.strftime("%Y%m%d") for b in bars]
        # ascending
        assert dates == sorted(dates), "bars not ascending"
        # no duplicates
        assert len(dates) == len(set(dates)), "duplicate dates"
        # contains both pages
        assert "20260101" in dates
        assert "20250901" in dates
        assert len(bars) == 20

    def test_overlap_deduped(self, tmp_path):
        """Pages with overlapping dates → duplicates removed."""

        # page1: 20260101–20260110
        page1_rows = [_make_overseas_row("202601%02d" % d) for d in range(1, 11)]
        # page2: 20260108–20260120 (overlap 20260108–20260110)
        page2_rows = [_make_overseas_row("202601%02d" % d) for d in range(8, 21)]

        call_count = [0]

        def handler(req):
            if str(req.url.path).endswith("/oauth2/tokenP"):
                return _token_resp()
            if "overseas-price" in req.url.path:
                n = call_count[0]; call_count[0] += 1
                return _overseas_page(page1_rows if n == 0 else page2_rows)
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        bars = kis.daily_bars_history("AAPL", "NASDAQ", "USD",
                                      lookback_days=500, max_pages=5)
        dates = [b.ts.strftime("%Y%m%d") for b in bars]
        assert len(dates) == len(set(dates)), "duplicate dates after overlap dedup"
        assert dates == sorted(dates)

    def test_stops_at_max_pages(self, tmp_path):
        """Pagination stops after max_pages pages even if data continues."""
        pages_served = [0]

        def handler(req):
            if str(req.url.path).endswith("/oauth2/tokenP"):
                return _token_resp()
            if "overseas-price" in req.url.path:
                n = pages_served[0]; pages_served[0] += 1
                # Each page: 5 bars; dates step back by 5 each page
                start_day = 300 - n * 5
                rows = [_make_overseas_row("20240101") for _ in range(5)]
                # Give unique dates per page
                import datetime as _dt
                base = _dt.date(2026, 1, 10) - _dt.timedelta(days=n * 5)
                rows = [_make_overseas_row((base - _dt.timedelta(days=i)).strftime("%Y%m%d"))
                        for i in range(5)]
                return _overseas_page(rows)
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        bars = kis.daily_bars_history("AAPL", "NASDAQ", "USD",
                                      lookback_days=9999, max_pages=3)
        assert pages_served[0] == 3, f"expected 3 pages, got {pages_served[0]}"

    def test_stops_on_empty_page(self, tmp_path):
        """Pagination stops when a page returns no bars."""
        call_count = [0]

        def handler(req):
            if str(req.url.path).endswith("/oauth2/tokenP"):
                return _token_resp()
            if "overseas-price" in req.url.path:
                n = call_count[0]; call_count[0] += 1
                if n == 0:
                    return _overseas_page([_make_overseas_row("20260101")])
                else:
                    return _overseas_page([])  # empty → stop
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        bars = kis.daily_bars_history("AAPL", "NASDAQ", "USD",
                                      lookback_days=500, max_pages=10)
        assert len(bars) == 1
        assert call_count[0] == 2  # tried second page, got empty, stopped

    def test_stops_when_lookback_exhausted(self, tmp_path):
        """Pagination stops when earliest bar exceeds lookback_days window."""
        import datetime as _dt

        call_count = [0]

        def handler(req):
            if str(req.url.path).endswith("/oauth2/tokenP"):
                return _token_resp()
            if "overseas-price" in req.url.path:
                n = call_count[0]; call_count[0] += 1
                if n == 0:
                    # Recent bars: today-ish
                    d = _dt.date(2026, 6, 1)
                    rows = [_make_overseas_row((d - _dt.timedelta(days=i)).strftime("%Y%m%d"))
                            for i in range(5)]
                    return _overseas_page(rows)
                else:
                    # Old bars: 10 years ago — beyond any lookback
                    d = _dt.date(2016, 1, 1)
                    rows = [_make_overseas_row((d - _dt.timedelta(days=i)).strftime("%Y%m%d"))
                            for i in range(5)]
                    return _overseas_page(rows)
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        # lookback_days=30 — page2 dates are ~3700 days back → stop after page2
        bars = kis.daily_bars_history("AAPL", "NASDAQ", "USD",
                                      lookback_days=30, max_pages=10)
        # Only bars within the 30-day window are kept (or possibly none from page2),
        # but pagination must stop (call_count == 2, not 10)
        assert call_count[0] == 2

    def test_result_ascending_sorted(self, tmp_path):
        """Result is always ascending by ts regardless of API return order."""
        # Page serves rows in reverse order (newest first, as KIS actually does)
        rows = [_make_overseas_row("202601%02d" % d) for d in range(10, 0, -1)]

        def handler(req):
            if str(req.url.path).endswith("/oauth2/tokenP"):
                return _token_resp()
            if "overseas-price" in req.url.path:
                return _overseas_page(rows)
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        bars = kis.daily_bars_history("AAPL", "NASDAQ", "USD",
                                      lookback_days=9999, max_pages=1)
        dates = [b.ts.strftime("%Y%m%d") for b in bars]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# KOSPI pagination tests
# ---------------------------------------------------------------------------

class TestKospiPagination:
    """KOSPI: window-backward pagination."""

    def test_two_windows_stitched_ascending(self, tmp_path):
        """Two KOSPI windows → stitched, ascending, deduped."""
        call_count = [0]

        def handler(req):
            if str(req.url.path).endswith("/oauth2/tokenP"):
                return _token_resp()
            if "domestic-stock" in req.url.path and "itemchartprice" in req.url.path:
                n = call_count[0]; call_count[0] += 1
                if n == 0:
                    rows = [_make_domestic_row("202601%02d" % d) for d in range(1, 6)]
                else:
                    rows = [_make_domestic_row("202509%02d" % d) for d in range(1, 6)]
                return _domestic_page(rows)
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        bars = kis.daily_bars_history("005930", "KOSPI", "KRW",
                                      lookback_days=500, max_pages=5)
        dates = [b.ts.strftime("%Y%m%d") for b in bars]
        assert dates == sorted(dates)
        assert len(dates) == len(set(dates))
        assert "20260101" in dates
        assert "20250901" in dates
        assert len(bars) == 10

    def test_kospi_stops_at_max_pages(self, tmp_path):
        pages = [0]

        def handler(req):
            if str(req.url.path).endswith("/oauth2/tokenP"):
                return _token_resp()
            if "domestic-stock" in req.url.path:
                import datetime as _dt
                n = pages[0]; pages[0] += 1
                base = _dt.date(2026, 6, 1) - _dt.timedelta(days=n * 10)
                rows = [_make_domestic_row((base - _dt.timedelta(days=i)).strftime("%Y%m%d"))
                        for i in range(5)]
                return _domestic_page(rows)
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        kis.daily_bars_history("005930", "KOSPI", "KRW",
                               lookback_days=9999, max_pages=2)
        assert pages[0] == 2

    def test_kospi_stops_on_empty_page(self, tmp_path):
        call_count = [0]

        def handler(req):
            if str(req.url.path).endswith("/oauth2/tokenP"):
                return _token_resp()
            if "domestic-stock" in req.url.path:
                n = call_count[0]; call_count[0] += 1
                if n == 0:
                    return _domestic_page([_make_domestic_row("20260101")])
                return _domestic_page([])
            return httpx.Response(404)

        kis = _kis(handler, tmp_path)
        bars = kis.daily_bars_history("005930", "KOSPI", "KRW",
                                      lookback_days=500, max_pages=10)
        assert len(bars) == 1
        assert call_count[0] == 2
