# trader/data/accumulator.py
"""RESEARCH ONLY — Resumable historical-data accumulator.

Incrementally builds a local Parquet dataset of daily OHLCV bars for a
broad universe (US S&P 500 + KR KOSPI large-caps) without triggering
Yahoo Finance 429 rate-limits.

Design:
  - A JSON manifest at ``research_data/_manifest.json`` tracks per-symbol
    status (pending / ok / cooldown / error) plus metadata.
  - Each ``run_once()`` call fetches the next N un-done symbols and sleeps
    between fetches to stay well under rate limits.
  - Re-running the accumulator picks up from where the previous run left off
    (resumable).
  - On a 429-like RuntimeError the affected provider is halted for the rest
    of the current run and the symbol is placed in a 24-hour cooldown.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

# How long (seconds) a symbol stays in cooldown after a 429
_COOLDOWN_SECS = 24 * 3600

# A symbol is considered "stale" (needs refresh) if its last successful
# fetch was more than this many days ago.
_STALE_DAYS = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _default_entry() -> dict[str, Any]:
    return {
        "status": "pending",
        "last_success": None,
        "first_date": None,
        "last_date": None,
        "error_count": 0,
        "last_error": None,
        "cooldown_until": None,
    }


def _key(market: str, ticker: str) -> str:
    return f"{market}|{ticker}"


# ---------------------------------------------------------------------------
# DataAccumulator
# ---------------------------------------------------------------------------

class DataAccumulator:
    """Resumable, rate-limit-safe accumulator for OHLCV research data.

    Parameters
    ----------
    provider:
        An object with a ``daily_history(ticker, market, refresh=True)``
        method (e.g. ResearchDataProvider).
    universe_list:
        List of (ticker, market) tuples describing the full target universe.
    manifest_path:
        Path to the JSON manifest file (created if absent).
    per_run:
        Maximum number of symbols to fetch in a single ``run_once()`` call.
    sleep:
        Injectable sleep callable (default ``time.sleep``).  Pass a no-op in
        tests to avoid actual waits.
    sleep_secs:
        Seconds to sleep between individual symbol fetches (default 25.0 for
        Yahoo rate-limit safety).
    now:
        Injectable clock callable returning float epoch seconds (default
        ``time.time``).
    """

    def __init__(
        self,
        provider: Any,
        universe_list: list[tuple[str, str]],
        manifest_path: str = "research_data/_manifest.json",
        per_run: int = 25,
        sleep: Callable[[float], None] = time.sleep,
        sleep_secs: float = 25.0,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._provider = provider
        self._universe = universe_list  # [(ticker, market), ...]
        self._manifest_path = manifest_path
        self._per_run = per_run
        self._sleep = sleep
        self._sleep_secs = sleep_secs
        self._now = now

    # ------------------------------------------------------------------
    # Manifest I/O
    # ------------------------------------------------------------------

    def _load_manifest(self) -> dict[str, Any]:
        if os.path.exists(self._manifest_path):
            try:
                with open(self._manifest_path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Manifest unreadable (%s); starting fresh.", exc)
        return {}

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self._manifest_path), exist_ok=True)
        # Atomic write via temp file + rename
        dir_ = os.path.dirname(self._manifest_path) or "."
        fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2)
            os.replace(tmp, self._manifest_path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Select next batch
    # ------------------------------------------------------------------

    def select_next(self) -> list[tuple[str, str]]:
        """Return up to *per_run* symbols that need fetching.

        Selection criteria (in priority order):
          1. status == "pending"  (never fetched)
          2. status == "ok" but last_success older than _STALE_DAYS days
        Symbols currently in cooldown (cooldown_until > now) are skipped.
        Within each group, nulls-first ordering on last_success ensures
        never-fetched symbols come before stale ones.
        """
        manifest = self._load_manifest()
        now = self._now()
        stale_cutoff = now - _STALE_DAYS * 86400

        pending: list[tuple[str, str]] = []
        stale: list[tuple[str, str]] = []

        for ticker, market in self._universe:
            k = _key(market, ticker)
            entry = manifest.get(k, _default_entry())

            # Skip if in active cooldown
            cooldown_until = entry.get("cooldown_until")
            if cooldown_until is not None and cooldown_until > now:
                continue

            status = entry.get("status", "pending")
            last_success = entry.get("last_success")  # ISO string or None

            if status == "pending" or last_success is None:
                pending.append((ticker, market))
            elif status == "ok":
                # Convert last_success ISO → epoch for comparison
                try:
                    ls_epoch = datetime.fromisoformat(last_success).timestamp()
                except (ValueError, TypeError):
                    ls_epoch = 0.0
                if ls_epoch < stale_cutoff:
                    stale.append((ticker, market))
            # status == "error" or "cooldown" with expired window → treat as pending
            elif status in ("error", "cooldown"):
                pending.append((ticker, market))

        selected = (pending + stale)[: self._per_run]
        return selected

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run_once(self) -> dict[str, Any]:
        """Fetch the next batch of symbols and update the manifest.

        Returns a summary dict::

            {
                "fetched": int,     # successfully fetched this run
                "cooled": int,      # symbols placed in cooldown (429)
                "errored": int,     # symbols that hit non-429 errors
                "remaining_pending": int,  # symbols still needing work
            }

        Behaviour on 429:
          Sets the symbol's status to "cooldown" with cooldown_until = now+24h,
          then STOPS fetching from this provider for the rest of the run
          (avoids hammering Yahoo further).
        """
        targets = self.select_next()
        manifest = self._load_manifest()

        fetched = 0
        cooled = 0
        errored = 0
        halted = False  # True after the first 429 this run

        for i, (ticker, market) in enumerate(targets):
            if halted:
                break

            # Sleep between fetches (skip before the first one)
            if i > 0:
                self._sleep(self._sleep_secs)

            k = _key(market, ticker)
            entry = manifest.get(k, _default_entry())

            try:
                bars = self._provider.daily_history(ticker, market, refresh=True)

                # Success — update manifest
                entry["status"] = "ok"
                entry["last_success"] = _now_iso()
                entry["cooldown_until"] = None
                if bars:
                    dates_sorted = sorted(b.ts.date().isoformat() for b in bars)
                    entry["first_date"] = dates_sorted[0]
                    entry["last_date"] = dates_sorted[-1]
                manifest[k] = entry
                self._save_manifest(manifest)
                fetched += 1
                logger.info("OK  %s:%s  bars=%d", market, ticker, len(bars))

            except RuntimeError as exc:
                msg = str(exc)
                is_rate_limit = "429" in msg or "rate-limit" in msg.lower() or "rate_limit" in msg.lower()

                if is_rate_limit:
                    entry["status"] = "cooldown"
                    entry["cooldown_until"] = self._now() + _COOLDOWN_SECS
                    entry["last_error"] = msg[:300]
                    manifest[k] = entry
                    self._save_manifest(manifest)
                    cooled += 1
                    halted = True  # stop hammering for this run
                    logger.warning("COOLDOWN  %s:%s  (429 — halting run)", market, ticker)
                else:
                    entry["status"] = "error"
                    entry["error_count"] = entry.get("error_count", 0) + 1
                    entry["last_error"] = msg[:300]
                    manifest[k] = entry
                    self._save_manifest(manifest)
                    errored += 1
                    logger.warning("ERROR  %s:%s  %s", market, ticker, msg[:120])

        # Count remaining pending (reload manifest for accuracy)
        manifest = self._load_manifest()
        now = self._now()
        remaining = 0
        for ticker, market in self._universe:
            k = _key(market, ticker)
            entry = manifest.get(k, _default_entry())
            status = entry.get("status", "pending")
            cooldown_until = entry.get("cooldown_until")
            in_cooldown = cooldown_until is not None and cooldown_until > now
            if not in_cooldown and status in ("pending", "error"):
                remaining += 1
            elif status == "ok":
                last_success = entry.get("last_success")
                try:
                    ls_epoch = datetime.fromisoformat(last_success).timestamp() if last_success else 0.0
                except (ValueError, TypeError):
                    ls_epoch = 0.0
                stale_cutoff = now - _STALE_DAYS * 86400
                if ls_epoch < stale_cutoff:
                    remaining += 1

        return {
            "fetched": fetched,
            "cooled": cooled,
            "errored": errored,
            "remaining_pending": remaining,
        }

    # ------------------------------------------------------------------
    # Progress helper
    # ------------------------------------------------------------------

    def progress(self) -> dict[str, int]:
        """Return counts of {total, done, pending, cooldown, error}."""
        manifest = self._load_manifest()
        now = self._now()
        counts: dict[str, int] = {
            "total": len(self._universe),
            "done": 0,
            "pending": 0,
            "cooldown": 0,
            "error": 0,
        }
        stale_cutoff = now - _STALE_DAYS * 86400
        for ticker, market in self._universe:
            k = _key(market, ticker)
            entry = manifest.get(k, _default_entry())
            status = entry.get("status", "pending")
            cooldown_until = entry.get("cooldown_until")
            in_cooldown = cooldown_until is not None and cooldown_until > now

            if in_cooldown:
                counts["cooldown"] += 1
            elif status == "ok":
                last_success = entry.get("last_success")
                try:
                    ls_epoch = datetime.fromisoformat(last_success).timestamp() if last_success else 0.0
                except (ValueError, TypeError):
                    ls_epoch = 0.0
                if ls_epoch >= stale_cutoff:
                    counts["done"] += 1
                else:
                    counts["pending"] += 1
            elif status == "error":
                counts["error"] += 1
            else:
                counts["pending"] += 1
        return counts
