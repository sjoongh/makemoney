# Paper-Forward Signal Journal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a paper-forward signal journal that records each daily trading decision using only information known at decision time, and a separate reconciliation step that appends realized forward returns without touching the decision records.

**Architecture:** Each daily decision is serialized as an append-only JSONL record with a content hash for idempotency. A separate reconciliation pass reads the raw journal plus fresh bar data, computes forward returns at 1/5/20-day horizons, and writes derived `*.reconciled.jsonl` files—never mutating the source records. DailyActEngine is extended to capture signals and combined score explicitly so they can be journaled without changing observable order behavior.

**Tech Stack:** Python 3.9, dataclasses, hashlib (stdlib), pathlib, json, pytest with tmp_path, existing FusionEngine/DailyActEngine/BarEvent/NormalizedSignal/OrderEvent types.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `trader/live/journal.py` | DecisionRecord dataclass, decision_hash, SignalJournal (append/load), build_record, reconcile |
| Modify | `trader/strategy/fusion_engine.py` | Add public `combined_score(signals)` method; keep `_combine` as alias |
| Modify | `trader/live/daily.py` | Add optional `journal` + `run_id` params; journal each decision |
| Modify | `trader/app/run_daily.py` | Wire SignalJournal + deterministic run_id |
| Create | `trader/app/run_reconcile.py` | Load journal + bars, write reconciled file, print hit-rate summary |
| Modify | `.gitignore` | Add `paper_forward/` |
| Create | `tests/test_journal.py` | All journal + reconciliation tests |

---

## Task 1: Add `combined_score` to FusionEngine (no behavior change)

**Files:**
- Modify: `trader/strategy/fusion_engine.py`

- [ ] **Step 1.1: Write the failing test**

Add to `tests/test_fusion_engine.py` at the bottom:

```python
def test_combined_score_public_method_equals_combine():
    """combined_score(signals) must equal the private _combine output."""
    from datetime import datetime, timezone, timedelta
    from trader.core.events import Symbol, Market, BarEvent, NormalizedSignal

    sym = Symbol("AAPL", Market.NASDAQ, "USD")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [BarEvent(sym, t0 + timedelta(days=i), float(i+1), float(i+1),
                     float(i+1), float(i+1), 100) for i in range(6)]

    eng = _engine()
    for b in bars[:5]:
        eng.warmup_bar(b)

    signals = eng.observe_bar(bars[5])
    assert hasattr(eng, "combined_score"), "FusionEngine must expose combined_score"
    assert eng.combined_score(signals) == eng._combine(signals)
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest tests/test_fusion_engine.py::test_combined_score_public_method_equals_combine -v
```

Expected: `FAILED` — `AttributeError: 'FusionEngine' object has no attribute 'combined_score'`

- [ ] **Step 1.3: Add `combined_score` to FusionEngine**

In `trader/strategy/fusion_engine.py`, add after `_combine`:

```python
    def combined_score(self, signals: list) -> float:
        """Public alias for _combine — returns the weighted combined score."""
        return self._combine(signals)
```

The full updated class body (methods in order): `on_fill`, `_combine`, `combined_score`, `observe_bar`, `decide_orders`, `warmup_bar`, `on_bar`.

- [ ] **Step 1.4: Run test to verify it passes**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest tests/test_fusion_engine.py -v
```

Expected: All fusion engine tests PASS.

- [ ] **Step 1.5: Run full suite to confirm parity untouched**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest -q
```

Expected: All existing tests PASS (no regressions).

---

## Task 2: Write failing tests for journal core

**Files:**
- Create: `tests/test_journal.py`

- [ ] **Step 2.1: Create `tests/test_journal.py` with all journal tests**

```python
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
```

- [ ] **Step 2.2: Run tests to confirm they ALL fail (module not found)**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest tests/test_journal.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'DecisionRecord' from 'trader.live.journal'` (or ModuleNotFoundError).

---

## Task 3: Implement `trader/live/journal.py` — journal core

**Files:**
- Create: `trader/live/journal.py`

- [ ] **Step 3.1: Create `trader/live/journal.py`**

```python
# trader/live/journal.py
"""Paper-forward signal journal.

Records each daily decision using ONLY information known at time T.
A separate reconciliation step later appends realized forward returns.
Outcomes are NEVER fed back into decisions.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass, field, asdict
from typing import Optional

from trader.core.events import BarEvent, NormalizedSignal, OrderEvent, Side

JOURNAL_VERSION = "1"


@dataclass(frozen=True)
class DecisionRecord:
    journal_version: str
    engine: str
    run_id: str
    market: str
    symbol: str
    bar_date: str          # ISO date string, e.g. "2026-01-02"
    key: str               # f"{engine}:{market}:{symbol}:{bar_date}"
    close: float
    currency: str
    source_scores: dict    # {source_name: score}
    source_confidences: dict  # {source_name: confidence}
    source_horizons: dict  # {source_name: horizon}
    combined_score: float
    target_weight: float
    action: str            # "BUY" | "SELL" | "HOLD"
    qty: int
    decision_price: float
    outcome: Optional[dict] = None


# Fields excluded from the content hash (must not influence the decision fingerprint)
_HASH_EXCLUDE = frozenset({"run_id", "outcome"})


def decision_hash(record: DecisionRecord) -> str:
    """SHA-256 of canonical JSON of decision fields, excluding run_id and outcome."""
    d = {k: v for k, v in asdict(record).items() if k not in _HASH_EXCLUDE}
    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_record(
    *,
    engine: str,
    run_id: str,
    bar: BarEvent,
    signals: list,
    combined: float,
    target_weight: float,
    orders: list,
) -> DecisionRecord:
    """Build a DecisionRecord from decision-time information only.

    - signals: list[NormalizedSignal] collected before decide_orders
    - combined: the weighted combined score
    - orders: the OrderEvent list returned by decide_orders (may be empty)
    - No look-ahead: all values derive from bar and signals, not future data.
    """
    bar_date = str(bar.ts.date())
    market = bar.symbol.market.value
    symbol = bar.symbol.ticker
    currency = bar.symbol.currency

    source_scores = {s.source: s.score for s in signals}
    source_confidences = {s.source: s.confidence for s in signals}
    source_horizons = {s.source: s.horizon for s in signals}

    # Derive action/qty from the first order for this symbol (there is at most one
    # order per symbol per bar in the current FusionEngine design).
    sym_orders = [o for o in orders if o.symbol == bar.symbol]
    if sym_orders:
        first = sym_orders[0]
        action = first.side.value   # "BUY" or "SELL"
        qty = first.quantity
    else:
        action = "HOLD"
        qty = 0

    key = f"{engine}:{market}:{symbol}:{bar_date}"

    return DecisionRecord(
        journal_version=JOURNAL_VERSION,
        engine=engine,
        run_id=run_id,
        market=market,
        symbol=symbol,
        bar_date=bar_date,
        key=key,
        close=bar.close,
        currency=currency,
        source_scores=source_scores,
        source_confidences=source_confidences,
        source_horizons=source_horizons,
        combined_score=combined,
        target_weight=target_weight,
        action=action,
        qty=qty,
        decision_price=bar.close,
    )


class SignalJournal:
    """Append-only journal for paper-forward signal decisions.

    File layout: {root}/{engine}/{market}/{year}.jsonl
    One JSON object per line. Idempotent: same key + same hash → no-op.
    """

    def __init__(self, root: str = "paper_forward") -> None:
        self.root = pathlib.Path(root)

    def _path(self, engine: str, market: str, year: int) -> pathlib.Path:
        return self.root / engine / market / f"{year}.jsonl"

    def append(self, record: DecisionRecord) -> bool:
        """Append record to journal. Returns True if written, False if skipped (idempotent).

        Raises ValueError if the same key exists with a different decision hash.
        """
        year = int(record.bar_date[:4])
        path = self._path(record.engine, record.market, year)
        path.parent.mkdir(parents=True, exist_ok=True)

        new_hash = decision_hash(record)

        # Scan existing lines for this key
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                existing = json.loads(line)
                if existing.get("key") == record.key:
                    if existing.get("_hash") == new_hash:
                        return False  # exact duplicate — skip
                    raise ValueError(
                        f"Decision hash mismatch for key={record.key!r}: "
                        f"stored={existing.get('_hash')!r}, new={new_hash!r}"
                    )

        # Append new record
        row = asdict(record)
        row["_hash"] = new_hash
        with path.open("a") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
        return True

    def load(self, engine: str, market: str, year: int) -> list[dict]:
        """Load all decision records for a given engine/market/year."""
        path = self._path(engine, market, year)
        if not path.exists():
            return []
        records = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records
```

- [ ] **Step 3.2: Run journal tests**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest tests/test_journal.py -v
```

Expected: All journal core tests PASS (reconciliation tests not yet written).

- [ ] **Step 3.3: Run full suite**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest -q
```

Expected: All tests PASS.

---

## Task 4: Commit 1

- [ ] **Step 4.1: Stage and commit**

```bash
cd /Users/manager/side/makemoney && git add trader/strategy/fusion_engine.py trader/live/journal.py tests/test_journal.py tests/test_fusion_engine.py && git commit -m "feat: paper-forward signal journal (decision-time records, idempotent)"
```

Expected: Commit created on branch `main`.

---

## Task 5: Write failing reconciliation tests

**Files:**
- Modify: `tests/test_journal.py` (append reconciliation tests)

- [ ] **Step 5.1: Append reconciliation tests to `tests/test_journal.py`**

Add the following at the bottom of `tests/test_journal.py`:

```python
# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------

from trader.live.journal import reconcile


class TestReconcile:
    """reconcile() computes forward returns from trading bars — no look-ahead."""

    def _make_bars(self, closes: list[float], start: datetime = None) -> list[BarEvent]:
        """Build BarEvent list ascending by date."""
        if start is None:
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        bars = []
        for i, c in enumerate(closes):
            ts = start + timedelta(days=i)
            bars.append(BarEvent(symbol=SYM, ts=ts, open=c, high=c, low=c, close=c, volume=100))
        return bars

    def _make_raw_record(self, bar_date_str: str, decision_price: float,
                         combined: float, score: float = 0.5) -> dict:
        """Return a raw dict as loaded from JSONL (mimics journal.load output)."""
        ts = datetime.fromisoformat(bar_date_str).replace(tzinfo=timezone.utc)
        signals = [_signal(score=score)]
        rec = build_record(
            engine="fusion_v1", run_id="run-test",
            bar=_bar(close=decision_price, ts=ts),
            signals=signals,
            combined=combined, target_weight=abs(combined),
            orders=[_buy_order()],
        )
        import dataclasses
        row = dataclasses.asdict(rec)
        from trader.live.journal import decision_hash
        row["_hash"] = decision_hash(rec)
        return row

    def test_positive_combined_rising_price_hit_true(self):
        """combined_score > 0 and price rises after decision → hit_5d True."""
        # Bars: indices 0..9, close = 100 + i
        closes = [100.0 + i for i in range(10)]
        bars = self._make_bars(closes)
        # Decision at bar index 0 (date=2026-01-01, close=100.0)
        record = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        bars_by_symbol = {"AAPL": bars}

        results = reconcile([record], bars_by_symbol, horizons=(1, 5))

        assert len(results) == 1
        outcome = results[0]["outcome"]
        assert outcome is not None
        # fwd_return_5d = close[0+5]/100.0 - 1 = 105/100 - 1 = 0.05
        assert abs(outcome["fwd_return_5d"] - 0.05) < 1e-9
        assert outcome["hit_5d"] is True

    def test_positive_combined_falling_price_hit_false(self):
        """combined_score > 0 and price falls → hit_5d False."""
        closes = [100.0 - i for i in range(10)]
        bars = self._make_bars(closes)
        record = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        bars_by_symbol = {"AAPL": bars}

        results = reconcile([record], bars_by_symbol, horizons=(5,))
        outcome = results[0]["outcome"]
        # fwd_return_5d = 95/100 - 1 = -0.05 → sign mismatch with combined > 0
        assert outcome["fwd_return_5d"] < 0
        assert outcome["hit_5d"] is False

    def test_insufficient_future_bars_returns_none(self):
        """If idx+N is out of range, fwd_return and hit are None."""
        # Only 3 bars total; decision at index 0 → 5d horizon out of range
        closes = [100.0, 101.0, 102.0]
        bars = self._make_bars(closes)
        record = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        bars_by_symbol = {"AAPL": bars}

        results = reconcile([record], bars_by_symbol, horizons=(5,))
        outcome = results[0]["outcome"]
        assert outcome["fwd_return_5d"] is None
        assert outcome["hit_5d"] is None

    def test_decision_fields_never_mutated(self):
        """reconcile must not alter any decision fields."""
        closes = [100.0 + i for i in range(10)]
        bars = self._make_bars(closes)
        record = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        original_combined = record["combined_score"]
        original_action = record["action"]
        bars_by_symbol = {"AAPL": bars}

        results = reconcile([record], bars_by_symbol, horizons=(1,))
        assert results[0]["combined_score"] == original_combined
        assert results[0]["action"] == original_action

    def test_multiple_records_reconciled_independently(self):
        """Two decisions at different bar indices are reconciled independently."""
        closes = [100.0 + i for i in range(10)]
        bars = self._make_bars(closes)
        rec0 = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        rec1 = self._make_raw_record("2026-01-02", decision_price=101.0, combined=0.5)
        bars_by_symbol = {"AAPL": bars}

        results = reconcile([rec0, rec1], bars_by_symbol, horizons=(1,))
        # fwd_return_1d for rec0: close[1]/100.0 - 1 = 0.01
        # fwd_return_1d for rec1: close[2]/101.0 - 1 ≈ 0.0099...
        assert results[0]["outcome"]["fwd_return_1d"] == pytest.approx(0.01)
        assert results[1]["outcome"]["fwd_return_1d"] == pytest.approx(102.0 / 101.0 - 1)

    def test_max_bar_date_in_outcome(self):
        """outcome must include max_bar_date = last date in the bar series."""
        closes = [100.0 + i for i in range(10)]
        bars = self._make_bars(closes)
        record = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        bars_by_symbol = {"AAPL": bars}

        results = reconcile([record], bars_by_symbol, horizons=(1,))
        # max date is 2026-01-09 (start=2026-01-01, index=9)
        assert results[0]["outcome"]["max_bar_date"] == "2026-01-10"
```

Wait — `max_bar_date` should be the date of the last bar. With start=2026-01-01 and 10 bars (indices 0..9), last bar is at index 9, date = 2026-01-10. Correct the test:

```python
    def test_max_bar_date_in_outcome(self):
        """outcome must include max_bar_date = last date in the bar series."""
        closes = [100.0 + i for i in range(10)]
        # start=2026-01-01, 10 bars → last ts = 2026-01-10
        bars = self._make_bars(closes, start=datetime(2026, 1, 1, tzinfo=timezone.utc))
        record = self._make_raw_record("2026-01-01", decision_price=100.0, combined=0.5)
        bars_by_symbol = {"AAPL": bars}

        results = reconcile([record], bars_by_symbol, horizons=(1,))
        last_bar_date = str(bars[-1].ts.date())   # "2026-01-10"
        assert results[0]["outcome"]["max_bar_date"] == last_bar_date
```

Actual complete test to add (use this version — the second replaces the first):

```python
# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------

from trader.live.journal import reconcile


class TestReconcile:
    """reconcile() computes forward returns from trading bars — no look-ahead."""

    def _make_bars(self, closes: list[float],
                   start: datetime = None) -> list[BarEvent]:
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
```

- [ ] **Step 5.2: Run reconciliation tests to confirm they fail**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest tests/test_journal.py::TestReconcile -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'reconcile' from 'trader.live.journal'`

---

## Task 6: Implement `reconcile` in `trader/live/journal.py`

**Files:**
- Modify: `trader/live/journal.py`

- [ ] **Step 6.1: Add `reconcile` function to `trader/live/journal.py`**

Append to the bottom of `trader/live/journal.py`:

```python
def reconcile(
    records: list[dict],
    bars_by_key_symbol: dict,
    horizons: tuple = (1, 5, 20),
) -> list[dict]:
    """Compute forward returns for each record and return enriched copies.

    Args:
        records: list of raw dicts as returned by SignalJournal.load()
        bars_by_key_symbol: dict mapping symbol ticker str → list[BarEvent]
                            (bars must be in ascending date order)
        horizons: tuple of ints (trading bars ahead) to compute forward returns for

    Returns:
        New list of dicts (copies), each with an 'outcome' key containing:
          fwd_return_Nd, hit_Nd for each N, and max_bar_date.
        Decision fields are NEVER mutated.
    """
    results = []
    for record in records:
        # Copy to avoid mutating the caller's dict
        rec = dict(record)

        symbol = rec["symbol"]
        bar_date = rec["bar_date"]
        decision_price = rec["decision_price"]
        combined_score_val = rec["combined_score"]

        bars = bars_by_key_symbol.get(symbol, [])
        # Find the index of the decision bar by date
        idx = None
        for i, b in enumerate(bars):
            if str(b.ts.date()) == bar_date:
                idx = i
                break

        max_bar_date = str(bars[-1].ts.date()) if bars else None

        outcome: dict = {"max_bar_date": max_bar_date}
        for n in horizons:
            key_ret = f"fwd_return_{n}d"
            key_hit = f"hit_{n}d"
            if idx is not None and (idx + n) < len(bars) and decision_price != 0:
                fwd_ret = bars[idx + n].close / decision_price - 1.0
                outcome[key_ret] = fwd_ret
                if combined_score_val != 0 and fwd_ret != 0:
                    hit = (combined_score_val > 0) == (fwd_ret > 0)
                    outcome[key_hit] = hit
                else:
                    outcome[key_hit] = None
            else:
                outcome[key_ret] = None
                outcome[key_hit] = None

        rec["outcome"] = outcome
        results.append(rec)
    return results
```

- [ ] **Step 6.2: Run all reconciliation tests**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest tests/test_journal.py -v
```

Expected: ALL journal tests PASS including `TestReconcile`.

- [ ] **Step 6.3: Run full suite**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest -q
```

Expected: All tests PASS.

---

## Task 7: Commit 2

- [ ] **Step 7.1: Stage and commit**

```bash
cd /Users/manager/side/makemoney && git add trader/live/journal.py tests/test_journal.py && git commit -m "feat: paper-forward reconciliation (forward returns + hit flags, no look-ahead)"
```

---

## Task 8: Wire journal into `DailyActEngine`

**Files:**
- Modify: `trader/live/daily.py`

- [ ] **Step 8.1: Update `DailyActEngine.__init__` to accept `journal` and `run_id`**

In `trader/live/daily.py`, update `__init__` signature and body:

```python
    def __init__(
        self,
        kis_client,
        strategy,
        fx: FxRates,
        symbols: list[tuple[str, str, str]],
        *,
        band: float = 0.01,
        dry_run: bool = True,
        ledger=None,
        max_staleness_days: int = 4,
        journal=None,
        run_id: str | None = None,
    ):
        self.kis = kis_client
        self.strategy = strategy
        self.fx = fx
        self.symbols = symbols
        self.band = band
        self.dry_run = dry_run
        self.ledger = ledger
        self.max_staleness_days = max_staleness_days
        self.journal = journal
        self.run_id = run_id
```

- [ ] **Step 8.2: Replace the `self.strategy.on_bar(latest_bar)` call with explicit observe/decide/journal flow**

Find this block in `DailyActEngine.run()`:

```python
            else:
                portfolio.mark(latest_bar)
                orders.extend(self.strategy.on_bar(latest_bar))
```

Replace with:

```python
            else:
                portfolio.mark(latest_bar)
                signals = self.strategy.observe_bar(latest_bar)
                combined = self.strategy.combined_score(signals)
                new_orders = self.strategy.decide_orders(latest_bar, signals)
                orders.extend(new_orders)
                if self.journal is not None and self.run_id is not None:
                    from trader.live.journal import build_record
                    rec = build_record(
                        engine=getattr(self.strategy, "name", "fusion_v1"),
                        run_id=self.run_id,
                        bar=latest_bar,
                        signals=signals,
                        combined=combined,
                        target_weight=combined,
                        orders=new_orders,
                    )
                    self.journal.append(rec)
```

Note: `FusionEngine` has no `.name` attribute by default — we use `getattr(..., "fusion_v1")` as a safe fallback. The test will rely on this fallback.

- [ ] **Step 8.3: Run full test suite — parity must stay green**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest -q
```

Expected: All tests PASS including `test_backtest_live_parity.py` and `test_daily_act.py`.

---

## Task 9: Wire journal into `run_daily.py`

**Files:**
- Modify: `trader/app/run_daily.py`

- [ ] **Step 9.1: Add `SignalJournal` import and wire into `main()`**

At the top of `run_daily.py`, add import after existing imports:

```python
from trader.live.journal import SignalJournal
```

In `main()`, after `ledger = RunLedger() if not dry_run else None`, add:

```python
    # Deterministic run_id from the current date (no wall clock; set at call time)
    # We'll set the actual run_id after we know the latest bar date — for now
    # initialize journal so DailyActEngine can call it.
    journal = SignalJournal(root="paper_forward")
```

Replace the `engine = DailyActEngine(...)` block with:

```python
    # run_id will be updated with the max bar date after fetching data.
    # For wiring purposes we use today's ISO date as a stable deterministic stamp.
    # DailyActEngine.run() sets signals from bar data, so bar date is the ground truth.
    # We inject it via a simple attribute; the engine reads self.run_id at decision time.
    from datetime import date
    run_id = f"run-{date.today().isoformat()}"

    engine = DailyActEngine(
        kis_client=kis,
        strategy=strategy,
        fx=fx,
        symbols=symbols,
        band=0.01,
        dry_run=dry_run,
        ledger=ledger,
        journal=journal,
        run_id=run_id,
    )
```

- [ ] **Step 9.2: Run full suite again**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest -q
```

Expected: All tests PASS.

---

## Task 10: Add `paper_forward/` to `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 10.1: Append `paper_forward/` to `.gitignore`**

Add to `.gitignore`:

```
paper_forward/
```

---

## Task 11: Create `trader/app/run_reconcile.py`

**Files:**
- Create: `trader/app/run_reconcile.py`

- [ ] **Step 11.1: Create `trader/app/run_reconcile.py`**

```python
# trader/app/run_reconcile.py
"""Reconciliation runner: load journal decisions, fetch fresh bars, write forward returns.

Usage:
    python -m trader.app.run_reconcile [--market KOSPI|NASDAQ|ALL] [--year 2026]

This script:
  1. Loads journal records from paper_forward/
  2. Fetches fresh daily bars via KIS (or loads from saved parquet if available)
  3. Calls reconcile() to compute forward returns at 1/5/20-day horizons
  4. Writes results to paper_forward/{engine}/{market}/{year}.reconciled.jsonl
  5. Prints a summary of per-source hit-rates at the 5-day horizon

HONEST CAVEAT: With a small number of reconciled records (N < 30), hit-rate estimates
are not statistically significant and should not be used for decisions.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
from collections import defaultdict
from datetime import date

from trader.live.journal import SignalJournal, reconcile

PAPER_FORWARD_ROOT = "paper_forward"
JOURNAL_ENGINE = "fusion_v1"


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip(); value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def _fetch_bars_via_kis(symbols: list[tuple[str, str, str]]) -> dict:
    """Fetch fresh bars from KIS. Returns dict: ticker → list[BarEvent]."""
    import httpx
    from trader.app.config import AppConfig
    from trader.execution.kis_client import KisClient

    PAPER_BASE = "https://openapivts.koreainvestment.com:29443"
    _load_dotenv()
    cfg = AppConfig.from_env()
    http = httpx.Client(base_url=PAPER_BASE, timeout=30)
    kis = KisClient(http, cfg.kis_app_key, cfg.kis_app_secret, cfg.kis_account,
                    paper=cfg.paper, min_interval=1.0)

    bars_by_symbol: dict = {}
    for ticker, market, currency in symbols:
        bars = kis.daily_bars(ticker, market, currency)
        bars_by_symbol[ticker] = sorted(bars, key=lambda b: b.ts)
    return bars_by_symbol


def _print_summary(reconciled: list[dict]) -> None:
    """Print per-source hit-rate at 5d horizon, with an honest caveat on small N."""
    source_hits: dict[str, list] = defaultdict(list)
    for rec in reconciled:
        outcome = rec.get("outcome") or {}
        hit = outcome.get("hit_5d")
        for source in rec.get("source_scores", {}):
            if hit is not None:
                source_hits[source].append(hit)

    total = len(reconciled)
    reconciled_count = sum(
        1 for r in reconciled
        if (r.get("outcome") or {}).get("fwd_return_5d") is not None
    )

    print(f"\n=== Reconciliation Summary ===")
    print(f"Total records : {total}")
    print(f"Reconciled (5d available): {reconciled_count}")
    print()

    if not source_hits:
        print("No reconciled hit data available yet.")
        print("(Expected on day 1 — insufficient forward bars.)")
    else:
        print(f"{'Source':<30} {'N':>5}  {'Hit-rate 5d':>12}")
        print("-" * 50)
        for source, hits in sorted(source_hits.items()):
            n = len(hits)
            rate = sum(hits) / n if n else float("nan")
            print(f"{source:<30} {n:>5}  {rate:>12.1%}")

    print()
    print("CAVEAT: With small N (< 30), hit-rate estimates are not statistically")
    print("significant and should NOT be used for trading decisions.")


def main(market: str = "ALL", year: int = None) -> None:
    if year is None:
        year = date.today().year

    from trader.app.run_daily import SYMBOLS, filter_symbols_by_market
    symbols = filter_symbols_by_market(SYMBOLS, market)
    if not symbols:
        print(f"No symbols for market={market!r}. Exiting.")
        return

    journal = SignalJournal(root=PAPER_FORWARD_ROOT)

    # Collect all records across markets for the target year
    markets_in_symbols = {m for _, m, _ in symbols}
    all_records: list[dict] = []
    for mkt in sorted(markets_in_symbols):
        records = journal.load(JOURNAL_ENGINE, mkt, year)
        all_records.extend(records)

    print(f"Loaded {len(all_records)} decision record(s) for year={year}.")

    if not all_records:
        print("No journal records found. Run run_daily first to generate records.")
        return

    # Fetch fresh bars
    print("Fetching fresh bars for reconciliation …")
    try:
        bars_by_symbol = _fetch_bars_via_kis(symbols)
    except Exception as exc:
        print(f"Could not fetch bars: {exc}")
        print("Cannot reconcile without fresh bar data.")
        return

    # Reconcile
    reconciled = reconcile(all_records, bars_by_symbol, horizons=(1, 5, 20))

    # Write derived reconciled files (never overwrite source)
    root = pathlib.Path(PAPER_FORWARD_ROOT)
    for mkt in sorted(markets_in_symbols):
        mkt_records = [r for r in reconciled if r.get("market") == mkt]
        if not mkt_records:
            continue
        out_path = root / JOURNAL_ENGINE / mkt / f"{year}.reconciled.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as f:
            for row in mkt_records:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        print(f"Wrote {len(mkt_records)} reconciled record(s) → {out_path}")

    _print_summary(reconciled)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconcile paper-forward journal")
    parser.add_argument("--market", choices=["NASDAQ", "KOSPI", "ALL"], default="ALL")
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()
    main(market=args.market, year=args.year)
```

- [ ] **Step 11.2: Run full test suite**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest -q
```

Expected: All tests PASS.

---

## Task 12: Commit 3

- [ ] **Step 12.1: Stage all new/modified files and commit**

```bash
cd /Users/manager/side/makemoney && git add trader/live/daily.py trader/app/run_daily.py trader/app/run_reconcile.py .gitignore && git commit -m "feat: wire signal journal into run_daily + run_reconcile entrypoint"
```

---

## Task 13: Live Verification

- [ ] **Step 13.1: Run dry-run and confirm journal record is written**

```bash
cd /Users/manager/side/makemoney && .venv/bin/python -m trader.app.run_daily --market KOSPI
```

Then:

```bash
find /Users/manager/side/makemoney/paper_forward -name "*.jsonl" | head -5
```

Then show the content:

```bash
cat $(find /Users/manager/side/makemoney/paper_forward -name "*.jsonl" | head -1)
```

Expected: A JSONL line with keys: `journal_version`, `engine`, `run_id`, `market`, `symbol`, `bar_date`, `key`, `close`, `currency`, `source_scores`, `source_confidences`, `source_horizons`, `combined_score`, `target_weight`, `action`, `qty`, `decision_price`, `outcome`, `_hash`.

- [ ] **Step 13.2: Run reconciliation and show summary**

```bash
cd /Users/manager/side/makemoney && .venv/bin/python -m trader.app.run_reconcile --market KOSPI
```

Expected output (day 1, no forward bars available yet):

```
Loaded N decision record(s) for year=2026.
Fetching fresh bars for reconciliation …
Wrote N reconciled record(s) → paper_forward/fusion_v1/KOSPI/2026.reconciled.jsonl

=== Reconciliation Summary ===
Total records : N
Reconciled (5d available): 0

No reconciled hit data available yet.
(Expected on day 1 — insufficient forward bars.)

CAVEAT: With small N (< 30), hit-rate estimates are not statistically
significant and should NOT be used for trading decisions.
```

- [ ] **Step 13.3: Final full suite run**

```bash
cd /Users/manager/side/makemoney && .venv/bin/pytest -q
```

Expected: All tests PASS, parity test green.

---

## Self-Review Checklist

**Spec coverage:**
- [x] FusionEngine `combined_score` public method → Task 1
- [x] `DecisionRecord` frozen dataclass with all required fields → Task 3
- [x] `decision_hash` excluding run_id/outcome → Task 3
- [x] `SignalJournal.append` idempotent with hash check → Task 3
- [x] `SignalJournal.load` → Task 3
- [x] `build_record` capturing per-source dicts, action/qty, decision_price → Task 3
- [x] `reconcile` with fwd_return_Nd, hit_Nd, no look-ahead → Task 6
- [x] Reconcile writes to `*.reconciled.jsonl`, never overwrites source → Task 11
- [x] DailyActEngine optional `journal`/`run_id`, journals each decision → Task 8
- [x] `run_daily.py` wires journal + deterministic run_id → Task 9
- [x] `paper_forward/` in `.gitignore` → Task 10
- [x] `run_reconcile.py` with hit-rate summary and honest caveat → Task 11
- [x] All test cases from spec: build_record captures, idempotent, hash mismatch ValueError, different dates coexist → Task 2/3
- [x] Reconciliation tests: known series with hit_5d True/False, insufficient bars → None → Task 5/6
- [x] Three commits with exact messages → Tasks 4, 7, 12

**Type consistency:**
- `combined_score` method on FusionEngine takes `list` (not typed for flexibility), matches usage in daily.py
- `build_record` kwargs exactly match usage in daily.py wire-up
- `reconcile(records, bars_by_key_symbol, horizons)` — `bars_by_key_symbol` is `dict[str, list[BarEvent]]` keyed by ticker string, consistent with `bars_by_symbol[ticker]` in run_reconcile
- `DecisionRecord.source_scores` typed as `dict` (not `dict[str,float]`) to avoid Python 3.9 subscription issues — consistent across all usages
