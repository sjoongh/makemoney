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
from dataclasses import dataclass, asdict
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

    def load(self, engine: str, market: str, year: int) -> list:
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


def reconcile(
    records: list,
    bars_by_key_symbol: dict,
    horizons: tuple = (1, 5, 20),
) -> list:
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
