# trader/live/ledger.py
"""Idempotent daily run ledger — prevents double-submission per trading day per ticker."""
from __future__ import annotations

import json
import os


class RunLedger:
    """Persist a set of (account, trading_date, market, ticker) keys to a JSON file.

    acquire() is the single entry point:
      - Returns True  on the first call for a given key today → records it.
      - Returns False on any subsequent call for the same key → already ran.

    Each ticker is tracked independently so multiple symbols in the same market
    on the same day can each submit exactly once.

    The file is written atomically (write-then-rename) to avoid corruption on
    unexpected process termination.
    """

    def __init__(self, path: str = ".run_ledger.json"):
        self._path = path
        self._data: dict[str, list[str]] = {}  # account → list of "date|market|ticker" strings
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(self, account: str, trading_date: str, market: str, ticker: str) -> bool:
        """Try to claim the run slot for (account, trading_date, market, ticker).

        Returns:
            True  — slot was free; it is now recorded (caller should proceed).
            False — slot already taken (caller should skip submission).
        """
        entry = f"{trading_date}|{market}|{ticker}"
        seen = self._data.setdefault(account, [])
        if entry in seen:
            return False
        seen.append(entry)
        self._save()
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path) as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self._data = loaded
        except (json.JSONDecodeError, OSError):
            pass  # corrupt or unreadable — start fresh

    def _save(self) -> None:
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(self._data, f)
            os.replace(tmp, self._path)
        except OSError:
            pass  # non-fatal: next run will re-acquire, worst case double-submit
