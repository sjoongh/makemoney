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
import shutil
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


def provider_for(market: str) -> str:
    """Return the data provider name for a given market string.

    Mirrors the dispatch logic in ResearchDataProvider.daily_history:
      KOSPI  → "naver"
      everything else (NASDAQ, NYSE, …) → "yahoo"

    This is used by run_once() to build a per-run per-provider cooldown set
    so that a Yahoo (US) 429 does not block Naver (KR) accumulation and
    vice-versa.
    """
    if market.upper() == "KOSPI":
        return "naver"
    return "yahoo"


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
    quarantine_dir:
        Directory to move corrupt parquets into when quality validation fails.
        Defaults to ``research_data/_quarantine``.  Override in tests to keep
        the filesystem side-effects hermetic (use a tmp_path sub-directory).
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
        quarantine_dir: str | None = None,
    ) -> None:
        self._provider = provider
        self._universe = universe_list  # [(ticker, market), ...]
        self._manifest_path = manifest_path
        self._per_run = per_run
        self._sleep = sleep
        self._sleep_secs = sleep_secs
        self._now = now
        # Default quarantine dir is a sibling of the manifest's parent dir
        if quarantine_dir is None:
            _data_dir = os.path.dirname(manifest_path) or "research_data"
            self._quarantine_dir = os.path.join(_data_dir, "_quarantine")
        else:
            self._quarantine_dir = quarantine_dir

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
        Within each provider group, nulls-first ordering on last_success ensures
        never-fetched symbols come before stale ones.

        The batch is assembled by round-robin across providers so that both
        yahoo (US) and naver (KR) symbols appear even when the universe is
        predominantly US.  This prevents a Yahoo 429 throttle from starving
        Naver/KR accumulation.
        """
        manifest = self._load_manifest()
        now = self._now()
        stale_cutoff = now - _STALE_DAYS * 86400

        # Collect eligible symbols grouped by provider, preserving
        # within-provider order: pending/error first, then stale.
        # dict preserves insertion order (Python 3.7+).
        per_provider: dict[str, list[tuple[str, str]]] = {}

        for ticker, market in self._universe:
            k = _key(market, ticker)
            entry = manifest.get(k, _default_entry())

            # Skip if in active cooldown
            cooldown_until = entry.get("cooldown_until")
            if cooldown_until is not None and cooldown_until > now:
                continue

            status = entry.get("status", "pending")
            last_success = entry.get("last_success")  # ISO string or None

            # quality_fail is terminal — never re-pick automatically
            if status == "quality_fail":
                continue

            eligible = False
            if status == "pending" or last_success is None:
                eligible = True
            elif status == "ok":
                try:
                    ls_epoch = datetime.fromisoformat(last_success).timestamp()
                except (ValueError, TypeError):
                    ls_epoch = 0.0
                if ls_epoch < stale_cutoff:
                    eligible = True
            elif status in ("error", "cooldown"):
                eligible = True

            if eligible:
                prov = provider_for(market)
                if prov not in per_provider:
                    per_provider[prov] = []
                per_provider[prov].append((ticker, market))

        # Round-robin across providers up to per_run total.
        # Use indices to advance through each provider's list.
        provider_lists = list(per_provider.values())
        indices = [0] * len(provider_lists)
        selected: list[tuple[str, str]] = []

        while len(selected) < self._per_run:
            added_this_round = False
            for i, lst in enumerate(provider_lists):
                if len(selected) >= self._per_run:
                    break
                if indices[i] < len(lst):
                    selected.append(lst[indices[i]])
                    indices[i] += 1
                    added_this_round = True
            if not added_this_round:
                break  # all providers exhausted

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
        # Per-run set of cooled provider names (e.g. "yahoo", "naver").
        # A 429 from one provider halts only that provider for the rest of
        # this run; symbols served by a different provider continue normally.
        cooled_providers: set[str] = set()

        first_per_provider: dict[str, bool] = {}  # track first call per provider for sleep

        for ticker, market in targets:
            prov_name = provider_for(market)
            if prov_name in cooled_providers:
                # This provider was rate-limited earlier this run — skip.
                continue

            # Sleep between fetches of the same provider (skip before the
            # very first fetch for each provider).
            if first_per_provider.get(prov_name, False):
                self._sleep(self._sleep_secs)
            else:
                first_per_provider[prov_name] = True

            k = _key(market, ticker)
            entry = manifest.get(k, _default_entry())

            try:
                bars = self._provider.daily_history(ticker, market, refresh=True)

                # Quality-gate: validate before accepting the fetch as "ok"
                quality_passed = True
                issue_codes: list[str] = []
                if bars:
                    from trader.data.quality import validate_bars  # local import avoids circular
                    report = validate_bars(bars)
                    quality_passed = report.passed
                    if not quality_passed:
                        issue_codes = [i.code for i in report.issues if i.severity == "FAIL"]

                if not quality_passed:
                    # Move the just-cached parquet to quarantine
                    cache_filename = f"{market.upper()}_{ticker}.parquet"
                    cache_dir = os.path.dirname(self._manifest_path) or "research_data"
                    cached_parquet = os.path.join(cache_dir, cache_filename)
                    if os.path.exists(cached_parquet):
                        os.makedirs(self._quarantine_dir, exist_ok=True)
                        dest = os.path.join(self._quarantine_dir, cache_filename)
                        shutil.move(cached_parquet, dest)
                        logger.warning(
                            "QUARANTINED %s:%s → %s  issues=%s",
                            market, ticker, dest, issue_codes,
                        )
                    else:
                        logger.warning(
                            "QUARANTINED %s:%s (no parquet found at %s)  issues=%s",
                            market, ticker, cached_parquet, issue_codes,
                        )
                    print(f"QUARANTINED {market}:{ticker}: {issue_codes}")
                    entry["status"] = "quality_fail"
                    entry["last_error"] = f"quality_fail: {issue_codes}"
                    entry["cooldown_until"] = None
                    manifest[k] = entry
                    self._save_manifest(manifest)
                    # Do NOT increment fetched — corrupt data is not a success
                else:
                    # Clean fetch — update manifest as "ok"
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
                    cooled_providers.add(prov_name)  # halt this provider for the run
                    logger.warning(
                        "COOLDOWN  %s:%s  (429 — halting %s for this run)",
                        market, ticker, prov_name,
                    )
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
        """Return counts of {total, done, pending, cooldown, error, quality_fail}."""
        manifest = self._load_manifest()
        now = self._now()
        counts: dict[str, int] = {
            "total": len(self._universe),
            "done": 0,
            "pending": 0,
            "cooldown": 0,
            "error": 0,
            "quality_fail": 0,
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
            elif status == "quality_fail":
                counts["quality_fail"] += 1
            else:
                counts["pending"] += 1
        return counts
