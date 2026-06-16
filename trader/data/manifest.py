# trader/data/manifest.py
"""Dataset manifests + content hashing for reproducibility (P0 foundation).

Every backtest must reference an immutable, hashed dataset snapshot so that:
  - results are reproducible across time
  - experiments can be compared exactly
  - changes in underlying data are detected loudly

Usage:
    from trader.data.manifest import (
        build_manifest, content_hash_of,
        save_manifest, load_manifest,
        save_bars_with_manifest,
        verify, current_git_commit,
    )
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from typing import Optional

from trader.core.events import BarEvent
from trader.data.storage import save_bars


# ---------------------------------------------------------------------------
# DatasetManifest
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DatasetManifest:
    """Immutable record describing a cached dataset snapshot.

    Fields
    ------
    dataset_id:     Human-readable name, e.g. "NASDAQ_AAPL" or "KOSPI_005930".
    created_ts:     ISO-8601 timestamp supplied by the caller (no wall-clock in core).
    symbols:        Sorted list of ticker strings present in the dataset.
    provider:       Data source name, e.g. "Yahoo", "Naver", "KIS".
    start_date:     ISO date of earliest bar (YYYY-MM-DD).
    end_date:       ISO date of latest bar  (YYYY-MM-DD).
    n_bars:         Total number of bars.
    adjustment:     "adjusted" | "raw" | "mixed" | "unknown".
    content_hash:   SHA-256 hex digest of the canonical bar serialisation.
    code_commit:    Git HEAD SHA when the manifest was created (may be None).
    quality_passed: Result of validate_bars() (may be None if not checked).
    """

    dataset_id: str
    created_ts: str
    symbols: list
    provider: str
    start_date: str
    end_date: str
    n_bars: int
    adjustment: str
    content_hash: str
    code_commit: Optional[str]
    quality_passed: Optional[bool]


# ---------------------------------------------------------------------------
# content_hash_of
# ---------------------------------------------------------------------------

def content_hash_of(bars: list[BarEvent]) -> str:
    """Deterministic SHA-256 over the canonical sorted bar tuple list.

    Canonical form per bar (sorted ascending by (ts, ticker)):
        (symbol.ticker, ts.isoformat(), round(o,8), round(h,8),
         round(l,8), round(c,8), int(v))

    Same bars in any original order → same hash.
    One changed bar → different hash.
    """
    sorted_bars = sorted(bars, key=lambda b: (b.ts, b.symbol.ticker))
    canonical: list[tuple] = [
        (
            b.symbol.ticker,
            b.ts.isoformat(),
            round(b.open,  8),
            round(b.high,  8),
            round(b.low,   8),
            round(b.close, 8),
            int(b.volume),
        )
        for b in sorted_bars
    ]
    # Use repr for a stable, unambiguous byte representation
    raw = repr(canonical).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# build_manifest
# ---------------------------------------------------------------------------

def build_manifest(
    bars: list[BarEvent],
    *,
    dataset_id: str,
    provider: str,
    adjustment: str,
    created_ts: str,
    code_commit: Optional[str] = None,
    quality_passed: Optional[bool] = None,
) -> DatasetManifest:
    """Derive a DatasetManifest from bars + caller-supplied metadata.

    Derives: symbols, start_date, end_date, n_bars, content_hash automatically.
    """
    if not bars:
        raise ValueError("Cannot build manifest from empty bars list")

    sorted_bars = sorted(bars, key=lambda b: (b.ts, b.symbol.ticker))
    symbols = sorted({b.symbol.ticker for b in bars})
    start_date = sorted_bars[0].ts.date().isoformat()
    end_date   = sorted_bars[-1].ts.date().isoformat()

    return DatasetManifest(
        dataset_id=dataset_id,
        created_ts=created_ts,
        symbols=symbols,
        provider=provider,
        start_date=start_date,
        end_date=end_date,
        n_bars=len(bars),
        adjustment=adjustment,
        content_hash=content_hash_of(bars),
        code_commit=code_commit,
        quality_passed=quality_passed,
    )


# ---------------------------------------------------------------------------
# save_manifest / load_manifest
# ---------------------------------------------------------------------------

def save_manifest(manifest: DatasetManifest, path: str) -> None:
    """Serialise manifest to JSON at *path*."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(asdict(manifest), fh, indent=2)


def load_manifest(path: str) -> DatasetManifest:
    """Deserialise manifest from JSON at *path*."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return DatasetManifest(**data)


# ---------------------------------------------------------------------------
# current_git_commit
# ---------------------------------------------------------------------------

def current_git_commit() -> Optional[str]:
    """Return the current git HEAD SHA (best-effort; None on any failure)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

def verify(manifest: DatasetManifest, bars: list[BarEvent]) -> bool:
    """Return True iff bars match the manifest's content_hash.

    Detects if the underlying data changed since the manifest was created.
    """
    return content_hash_of(bars) == manifest.content_hash


# ---------------------------------------------------------------------------
# save_bars_with_manifest — convenience helper for research data paths
# ---------------------------------------------------------------------------

def save_bars_with_manifest(
    bars: list[BarEvent],
    path: str,
    *,
    provider: str,
    adjustment: str,
    created_ts: str,
    dataset_id: Optional[str] = None,
    code_commit: Optional[str] = None,
    quality_passed: Optional[bool] = None,
) -> DatasetManifest:
    """Save parquet at *path* AND write a sidecar manifest at *path*.manifest.json.

    Args:
        bars:          The bars to persist.
        path:          Destination parquet file path.
        provider:      Source name, e.g. "Yahoo", "Naver", "KIS".
        adjustment:    "adjusted" | "raw" | "mixed" | "unknown".
        created_ts:    ISO-8601 creation timestamp (supplied by caller).
        dataset_id:    Optional explicit ID; defaults to basename without extension.
        code_commit:   Git SHA (use current_git_commit() at call site if desired).
        quality_passed: Result of validate_bars() if already run.

    Returns:
        The DatasetManifest that was written.
    """
    import os

    if dataset_id is None:
        dataset_id = os.path.splitext(os.path.basename(path))[0]

    manifest = build_manifest(
        bars,
        dataset_id=dataset_id,
        provider=provider,
        adjustment=adjustment,
        created_ts=created_ts,
        code_commit=code_commit,
        quality_passed=quality_passed,
    )

    save_bars(bars, path)
    save_manifest(manifest, path + ".manifest.json")
    return manifest


# ---------------------------------------------------------------------------
# print_manifest_stamp — for CLI runners
# ---------------------------------------------------------------------------

def print_manifest_stamp(manifest: DatasetManifest, bars: list[BarEvent]) -> None:
    """Print a one-line manifest stamp + loud WARNING if hash mismatch.

    Call this at the top of any backtest/evaluate report so every result is
    stamped with WHICH data + WHICH code produced it.
    """
    hash_prefix = manifest.content_hash[:12]
    quality_str = (
        "PASS" if manifest.quality_passed is True
        else "FAIL" if manifest.quality_passed is False
        else "unchecked"
    )
    commit_str = manifest.code_commit[:10] if manifest.code_commit else "unknown"

    print(
        f"[DATASET] id={manifest.dataset_id}  hash={hash_prefix}  "
        f"n={manifest.n_bars}  {manifest.start_date}→{manifest.end_date}  "
        f"quality={quality_str}  commit={commit_str}"
    )

    if not verify(manifest, bars):
        print(
            "WARNING: DATA CHANGED — content_hash mismatch between "
            f"manifest ({hash_prefix}) and current bars. "
            "Results may not be reproducible."
        )
