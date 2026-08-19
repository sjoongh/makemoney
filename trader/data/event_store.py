# trader/data/event_store.py
"""RESEARCH ONLY — parquet event store with manifests (free-data expansion §4).

One table per market (event_data/NASDAQ_events.parquet, …). ``save_events``
merges with any existing table, dedupes by ``source_id``, sorts by
``accepted_ts`` and writes parquet + a sidecar manifest whose content hash is
row-order independent (same events → same hash, so unchanged re-backfills are
detectable). Callers supply ``created_ts`` (no wall-clock in core, same rule
as trader/data/manifest.py).

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

REQUIRED_FIELDS = (
    "market",
    "symbol",
    "corp",
    "event_type",
    "title",
    "accepted_ts",
    "source_id",
    "url",
)


def load_events(path: str | Path) -> list[dict]:
    """Load all event rows ([] if the table doesn't exist yet)."""
    p = Path(path)
    if not p.exists():
        return []
    return pd.read_parquet(p).to_dict("records")


def _content_hash(rows: list[dict]) -> str:
    canon = sorted(
        (json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows),
    )
    h = hashlib.sha256()
    for line in canon:
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def save_events(path: str | Path, rows: list[dict], created_ts: str) -> int:
    """Merge ``rows`` into the table at ``path``; returns total rows stored."""
    for r in rows:
        missing = [f for f in REQUIRED_FIELDS if not str(r.get(f, "")).strip()]
        if missing:
            raise ValueError(f"event row missing {missing[0]}: {r!r}")
    # Dedupe by (symbol, source_id): dual share classes (GOOG/GOOGL) share one
    # CIK and therefore identical accession numbers — both rows must survive.
    merged: dict[tuple[str, str], dict] = {
        (r["symbol"], r["source_id"]): dict(r) for r in load_events(path)
    }
    for r in rows:
        merged[(r["symbol"], r["source_id"])] = dict(r)
    final = sorted(merged.values(), key=lambda r: (r["accepted_ts"], r["source_id"]))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(final).to_parquet(p, index=False)
    manifest = {
        "dataset_id": p.stem,
        "created_ts": created_ts,
        "n_rows": len(final),
        "content_hash": _content_hash(final),
    }
    Path(str(p) + ".manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return len(final)
