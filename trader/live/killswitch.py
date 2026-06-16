# trader/live/killswitch.py
"""Durable kill switch backed by a JSON file on disk.

Usage::

    ks = KillSwitch()
    if ks.is_active():
        print("Kill switch is active:", ks.status()["reason"])
        sys.exit(1)

    # From an operator terminal / monitoring script:
    ks.trip(reason="Drawdown exceeded 5%", source="operator")
    ks.clear()

The file is written atomically (write-then-rename is not used here for
simplicity — the file is small and the risk of a torn write is
negligible for a daily paper-trading system).  The file path is
configurable so tests can use temp directories.
"""
from __future__ import annotations

import json
import os
from typing import Optional


class KillSwitch:
    """File-backed durable kill switch.

    Args:
        path: Path to the JSON state file (default ``.kill_switch.json``
              in the current working directory).
    """

    def __init__(self, path: str = ".kill_switch.json") -> None:
        self._path = path

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def trip(
        self,
        reason: str,
        source: str,
        ts: Optional[str] = None,
    ) -> None:
        """Activate the kill switch.

        Args:
            reason: Human-readable description of why the switch was tripped.
            source: Who/what tripped it (e.g. "operator", "monitor_agent").
            ts: Optional ISO timestamp string.  If omitted, no ``ts`` key is
                written (keeps the serialisation deterministic in tests).
        """
        payload: dict = {
            "active": True,
            "reason": reason,
            "source": source,
        }
        if ts is not None:
            payload["ts"] = ts
        with open(self._path, "w") as f:
            json.dump(payload, f)

    def clear(self) -> None:
        """Deactivate the kill switch by removing the state file."""
        if os.path.exists(self._path):
            os.remove(self._path)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        """Return True if the kill switch file exists and ``active`` is True."""
        state = self._read()
        return bool(state.get("active", False))

    def status(self) -> dict:
        """Return the raw state dict (empty dict if file absent/unreadable)."""
        return self._read()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read(self) -> dict:
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path) as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
