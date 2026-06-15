# tests/test_journal.py
"""Tests for trader/live/journal.py — paper-forward signal journal (decision records)."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pytest

from trader.core.events import (
    BarEvent, Market, NormalizedSignal, OrderEvent, Side, Symbol,
)
from trader.live.journal import (
    DecisionRecord,
    SignalJournal,
    build_record,
    decision_hash,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
T0 = datetime(2026, 1, 2, tzinfo=timezone.utc)


def _bar(close: float = 150.0, ts: datetime = T0) -> BarEvent:
    return BarEvent(symbol=SYM, ts=ts, open=close, high=close, low=close,
                    close=close, volume=1000)


def _signal(source: str = "technical.ma", score: float = 0.6,
            confidence: float = 0.8, horizon: str = "5d") -> NormalizedSignal:
    return NormalizedSignal(source=source, symbol=SYM, ts=T0,
                            score=score, confidence=confidence, horizon=horizon)


def _buy_order() -> OrderEvent:
    from uuid import uuid4
    return OrderEvent(order_id=uuid4(), symbol=SYM, ts=T0,
                      side=Side.BUY, quantity=10)


# ---------------------------------------------------------------------------
# build_record
# ---------------------------------------------------------------------------

class TestBuildRecord:
    def test_captures_per_source_scores(self):
        signals = [
            _signal("src_a", score=0.5, confidence=0.7, horizon="1d"),
            _signal("src_b", score=-0.3, confidence=0.9, horizon="5d"),
        ]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(), signals=signals,
            combined=0.1, target_weight=0.3,
            orders=[_buy_order()],
        )
        assert rec.source_scores == {"src_a": 0.5, "src_b": -0.3}
        assert rec.source_confidences == {"src_a": 0.7, "src_b": 0.9}
        assert rec.source_horizons == {"src_a": "1d", "src_b": "5d"}

    def test_captures_combined_score(self):
        signals = [_signal("src_a", score=0.4, confidence=1.0)]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(), signals=signals,
            combined=0.4, target_weight=0.4,
            orders=[_buy_order()],
        )
        assert rec.combined_score == 0.4

    def test_action_buy_from_orders(self):
        signals = [_signal()]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(), signals=signals,
            combined=0.6, target_weight=0.6,
            orders=[_buy_order()],
        )
        assert rec.action == "BUY"
        assert rec.qty == 10

    def test_action_sell_from_orders(self):
        from uuid import uuid4
        sell_order = OrderEvent(order_id=uuid4(), symbol=SYM, ts=T0,
                                side=Side.SELL, quantity=5)
        signals = [_signal()]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(), signals=signals,
            combined=-0.6, target_weight=0.0,
            orders=[sell_order],
        )
        assert rec.action == "SELL"
        assert rec.qty == 5

    def test_action_hold_when_no_orders(self):
        signals = [_signal()]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(), signals=signals,
            combined=0.1, target_weight=0.1,
            orders=[],
        )
        assert rec.action == "HOLD"
        assert rec.qty == 0

    def test_decision_price_equals_bar_close(self):
        signals = [_signal()]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(close=123.45), signals=signals,
            combined=0.5, target_weight=0.5,
            orders=[_buy_order()],
        )
        assert rec.decision_price == 123.45

    def test_bar_date_is_iso_date_string(self):
        signals = [_signal()]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(ts=datetime(2026, 3, 15, tzinfo=timezone.utc)),
            signals=signals, combined=0.5, target_weight=0.5, orders=[],
        )
        assert rec.bar_date == "2026-03-15"

    def test_key_format(self):
        signals = [_signal()]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(ts=datetime(2026, 1, 2, tzinfo=timezone.utc)),
            signals=signals, combined=0.5, target_weight=0.5, orders=[],
        )
        assert rec.key == "fusion_v1:NASDAQ:AAPL:2026-01-02"

    def test_outcome_is_none_at_decision_time(self):
        signals = [_signal()]
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(), signals=signals,
            combined=0.5, target_weight=0.5, orders=[],
        )
        assert rec.outcome is None


# ---------------------------------------------------------------------------
# decision_hash
# ---------------------------------------------------------------------------

class TestDecisionHash:
    def test_hash_is_deterministic(self):
        signals = [_signal()]
        rec = build_record(
            engine="fusion_v1", run_id="run-abc",
            bar=_bar(), signals=signals,
            combined=0.5, target_weight=0.5, orders=[_buy_order()],
        )
        # Build identical record with DIFFERENT run_id
        rec2 = build_record(
            engine="fusion_v1", run_id="run-xyz",
            bar=_bar(), signals=signals,
            combined=0.5, target_weight=0.5, orders=[_buy_order()],
        )
        # run_id is excluded from hash → hashes must be equal
        assert decision_hash(rec) == decision_hash(rec2)

    def test_hash_differs_on_different_score(self):
        signals_a = [_signal(score=0.5)]
        signals_b = [_signal(score=0.3)]
        rec_a = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(), signals=signals_a,
            combined=0.5, target_weight=0.5, orders=[],
        )
        rec_b = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(), signals=signals_b,
            combined=0.3, target_weight=0.3, orders=[],
        )
        assert decision_hash(rec_a) != decision_hash(rec_b)


# ---------------------------------------------------------------------------
# SignalJournal.append + load
# ---------------------------------------------------------------------------

class TestSignalJournalAppend:
    def _rec(self, bar_date_str: str = "2026-01-02",
             score: float = 0.5, run_id: str = "run-20260102") -> DecisionRecord:
        ts = datetime.fromisoformat(bar_date_str).replace(tzinfo=timezone.utc)
        signals = [_signal(score=score)]
        return build_record(
            engine="fusion_v1", run_id=run_id,
            bar=_bar(ts=ts), signals=signals,
            combined=score, target_weight=score, orders=[_buy_order()],
        )

    def test_append_returns_true_on_first_write(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        rec = self._rec()
        assert journal.append(rec) is True

    def test_file_has_exactly_one_line_after_first_append(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        rec = self._rec()
        journal.append(rec)
        lines = (tmp_path / "pf" / "fusion_v1" / "NASDAQ" / "2026.jsonl").read_text().splitlines()
        assert len(lines) == 1

    def test_idempotent_same_key_same_hash_returns_false(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        rec = self._rec()
        journal.append(rec)
        result = journal.append(rec)
        assert result is False

    def test_idempotent_no_duplicate_lines_in_file(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        rec = self._rec()
        journal.append(rec)
        journal.append(rec)
        lines = (tmp_path / "pf" / "fusion_v1" / "NASDAQ" / "2026.jsonl").read_text().splitlines()
        assert len(lines) == 1

    def test_same_key_different_hash_raises_value_error(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        rec_a = self._rec(score=0.5)
        rec_b = self._rec(score=0.9)  # same key, different combined_score → different hash
        journal.append(rec_a)
        with pytest.raises(ValueError, match="hash mismatch"):
            journal.append(rec_b)

    def test_different_bar_dates_coexist_in_same_file(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        rec1 = self._rec(bar_date_str="2026-01-02")
        rec2 = self._rec(bar_date_str="2026-01-03")
        journal.append(rec1)
        journal.append(rec2)
        lines = (tmp_path / "pf" / "fusion_v1" / "NASDAQ" / "2026.jsonl").read_text().splitlines()
        assert len(lines) == 2

    def test_file_path_uses_year_from_bar_date(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        rec = self._rec(bar_date_str="2025-12-31")
        journal.append(rec)
        expected = tmp_path / "pf" / "fusion_v1" / "NASDAQ" / "2025.jsonl"
        assert expected.exists()


class TestSignalJournalLoad:
    def test_load_returns_list_of_dicts(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        ts = datetime(2026, 1, 2, tzinfo=timezone.utc)
        rec = build_record(
            engine="fusion_v1", run_id="run-20260102",
            bar=_bar(ts=ts), signals=[_signal()],
            combined=0.5, target_weight=0.5, orders=[_buy_order()],
        )
        journal.append(rec)
        loaded = journal.load("fusion_v1", "NASDAQ", 2026)
        assert isinstance(loaded, list)
        assert len(loaded) == 1
        assert loaded[0]["key"] == rec.key

    def test_load_nonexistent_returns_empty_list(self, tmp_path):
        journal = SignalJournal(root=str(tmp_path / "pf"))
        result = journal.load("fusion_v1", "NASDAQ", 2099)
        assert result == []


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------

from trader.live.journal import reconcile


class TestReconcile:
    """reconcile() computes forward returns from trading bars — no look-ahead."""

    def _make_bars(self, closes: list,
                   start: datetime = None) -> list:
        if start is None:
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        bars = []
        for i, c in enumerate(closes):
            ts = start + timedelta(days=i)
            bars.append(
                BarEvent(symbol=SYM, ts=ts, open=c, high=c, low=c, close=c, volume=100)
            )
        return bars

    def _make_raw_record(self, bar_date_str: str, decision_price: float,
                         combined: float, score: float = 0.5) -> dict:
        import dataclasses
        ts = datetime.fromisoformat(bar_date_str).replace(tzinfo=timezone.utc)
        signals = [_signal(score=score)]
        rec = build_record(
            engine="fusion_v1", run_id="run-test",
            bar=_bar(close=decision_price, ts=ts),
            signals=signals,
            combined=combined, target_weight=abs(combined),
            orders=[_buy_order()],
        )
        row = dataclasses.asdict(rec)
        row["_hash"] = decision_hash(rec)
        return row

    def test_positive_combined_rising_price_hit_true(self):
        closes = [100.0 + i for i in range(10)]
        bars = self._make_bars(closes)
        record = self._make_raw_record(
            "2026-01-01", decision_price=100.0, combined=0.5
        )
        results = reconcile([record], {"AAPL": bars}, horizons=(1, 5))
        outcome = results[0]["outcome"]
        assert outcome is not None
        assert abs(outcome["fwd_return_5d"] - 0.05) < 1e-9
        assert outcome["hit_5d"] is True

    def test_positive_combined_falling_price_hit_false(self):
        closes = [100.0 - i for i in range(10)]
        bars = self._make_bars(closes)
        record = self._make_raw_record(
            "2026-01-01", decision_price=100.0, combined=0.5
        )
        results = reconcile([record], {"AAPL": bars}, horizons=(5,))
        outcome = results[0]["outcome"]
        assert outcome["fwd_return_5d"] < 0
        assert outcome["hit_5d"] is False

    def test_insufficient_future_bars_returns_none(self):
        closes = [100.0, 101.0, 102.0]
        bars = self._make_bars(closes)
        record = self._make_raw_record(
            "2026-01-01", decision_price=100.0, combined=0.5
        )
        results = reconcile([record], {"AAPL": bars}, horizons=(5,))
        outcome = results[0]["outcome"]
        assert outcome["fwd_return_5d"] is None
        assert outcome["hit_5d"] is None

    def test_decision_fields_never_mutated(self):
        closes = [100.0 + i for i in range(10)]
        bars = self._make_bars(closes)
        record = self._make_raw_record(
            "2026-01-01", decision_price=100.0, combined=0.5
        )
        orig_combined = record["combined_score"]
        orig_action = record["action"]
        results = reconcile([record], {"AAPL": bars}, horizons=(1,))
        assert results[0]["combined_score"] == orig_combined
        assert results[0]["action"] == orig_action

    def test_multiple_records_reconciled_independently(self):
        closes = [100.0 + i for i in range(10)]
        bars = self._make_bars(closes)
        rec0 = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        rec1 = self._make_raw_record("2026-01-02", decision_price=101.0, combined=0.5)
        results = reconcile([rec0, rec1], {"AAPL": bars}, horizons=(1,))
        assert results[0]["outcome"]["fwd_return_1d"] == pytest.approx(0.01)
        assert results[1]["outcome"]["fwd_return_1d"] == pytest.approx(102.0 / 101.0 - 1)

    def test_max_bar_date_in_outcome(self):
        closes = [100.0 + i for i in range(10)]
        bars = self._make_bars(closes, start=datetime(2026, 1, 1, tzinfo=timezone.utc))
        record = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        results = reconcile([record], {"AAPL": bars}, horizons=(1,))
        last_bar_date = str(bars[-1].ts.date())
        assert results[0]["outcome"]["max_bar_date"] == last_bar_date
