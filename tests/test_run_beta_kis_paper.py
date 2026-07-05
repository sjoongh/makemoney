# tests/test_run_beta_kis_paper.py
"""Money-path coverage for the ONLY KIS-credential runner.

Drives run_beta_kis_paper.main() with monkeypatched seams (no network, no real
account) to lock every guard: idempotency, FX gate, data-staleness abort,
pre-trade caps, dry-run, HOLD, and the happy path. The load-bearing invariant is
that submit_order is called ONLY when a real order should go out — every refuse
path must leave submit_calls empty.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from trader.app import run_beta_kis_paper as R

KST = timezone(timedelta(hours=9))


class FakeKis:
    account = "50193330"

    def __init__(self, *, cash=100_000_000.0, nass=100_000_000.0, ovr_cost=0.0,
                 positions=None, marks=None, fx=1500.0):
        self._snap = {
            "cash_krw": cash, "nass_krw": nass, "ovr_purchase_krw": ovr_cost,
            "positions": positions or {}, "marks": marks or {},
        }
        self._fx = fx
        self.submit_calls = []

    def account_snapshot(self):
        return self._snap

    def usd_krw_rate(self, default=-1.0):
        return self._fx

    def submit_order(self, ticker, market, side, quantity, price=0.0, order_type="00"):
        self.submit_calls.append((ticker, market, side, quantity, price, order_type))
        return "ODNO-TEST-1"


@pytest.fixture
def wire(monkeypatch, tmp_path):
    """Patch all external seams; return a helper to run main() with a FakeKis."""
    monkeypatch.chdir(tmp_path)          # TRACK_PATH / status.html / heartbeat → tmp
    monkeypatch.setattr(R, "_load_dotenv", lambda: None)
    monkeypatch.setattr(R, "_etf_native_price", lambda cfg: 745.0)
    monkeypatch.setattr(R, "live_allowed", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(R.hb, "record", lambda *a, **k: None)
    monkeypatch.setenv("KIS_APP_KEY", "x")
    # fresh index by default (yesterday), exposure 1.0
    today = datetime.now(tz=KST).date()
    state = {"dated": [(today - timedelta(days=1), 0.001)], "exposure": 1.0}
    monkeypatch.setattr(R, "_load_panel", lambda idx: {"x": [1]})
    monkeypatch.setattr(R, "robust_index_returns", lambda panel, **k: state["dated"])
    monkeypatch.setattr(R, "latest_exposure", lambda rets, **k: state["exposure"])

    def run(kis, argv, state_over=None):
        if state_over:
            state.update(state_over)
        monkeypatch.setattr(R, "build_kis_client", lambda: kis)
        return R.main(argv)

    run.state = state
    run.tmp = tmp_path
    return run


def _track_lines(tmp):
    p = tmp / "beta_kis_track.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


# ── happy path ────────────────────────────────────────────────────────────

def test_us_happy_path_submits(wire):
    kis = FakeKis()
    rc = wire(kis, ["--market", "US", "--live", "--capital-frac", "0.5"])
    assert rc == 0
    assert len(kis.submit_calls) == 1
    tkr, mkt, side, qty, price, otype = kis.submit_calls[0]
    assert (tkr, mkt, side, otype) == ("SPY", "NASDAQ", "BUY", "00")
    assert qty > 0 and price > 745.0            # limit priced through market
    rec = _track_lines(wire.tmp)[-1]
    assert rec["submitted_odno"] == "ODNO-TEST-1" and rec["live"] is True


# ── refuse paths: submit must NOT be called ─────────────────────────────────

def test_dry_run_never_submits(wire):
    kis = FakeKis()
    rc = wire(kis, ["--market", "US"])            # no --live
    assert rc == 0
    assert kis.submit_calls == []


def test_idempotency_skips_second_same_day(wire):
    # pre-seed today's submitted US line
    today = datetime.now(tz=KST).date().isoformat()
    (wire.tmp / "beta_kis_track.jsonl").write_text(json.dumps({
        "market": "US", "live": True, "submitted_odno": "PRIOR", "kst_date": today}) + "\n")
    kis = FakeKis()
    rc = wire(kis, ["--market", "US", "--live"])
    assert rc == 0
    assert kis.submit_calls == []                 # guarded


def test_fx_gate_aborts_us(wire):
    kis = FakeKis(fx=-1.0)                         # FX unavailable
    rc = wire(kis, ["--market", "US", "--live"])
    assert rc == 1
    assert kis.submit_calls == []


def test_stale_data_aborts(wire):
    kis = FakeKis()
    old = datetime.now(tz=KST).date() - timedelta(days=30)
    rc = wire(kis, ["--market", "US", "--live"], state_over={"dated": [(old, 0.001)]})
    assert rc == 1
    assert kis.submit_calls == []


def test_pretrade_notional_cap_refuses(wire):
    # capital-frac 1.0 + exposure 1.0 → ~100M target >> 60M notional cap
    kis = FakeKis()
    rc = wire(kis, ["--market", "US", "--live", "--capital-frac", "1.0"])
    assert rc == 1
    assert kis.submit_calls == []


def test_hold_within_band_no_submit(wire):
    # already at target: exposure 0 and no shares → HOLD
    kis = FakeKis()
    rc = wire(kis, ["--market", "US", "--live"], state_over={"exposure": 0.0})
    assert rc == 0
    assert kis.submit_calls == []


def test_live_gate_refused_blocks_submit(wire, monkeypatch):
    monkeypatch.setattr(R, "live_allowed", lambda *a, **k: (False, "killswitch"))
    kis = FakeKis()
    rc = wire(kis, ["--market", "US", "--live"])
    assert kis.submit_calls == []                 # gate refused → no order
