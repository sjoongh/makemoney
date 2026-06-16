# tests/test_killswitch.py
"""Tests for trader/live/killswitch.py — durable kill switch."""
from __future__ import annotations

import os
import tempfile

import pytest

from trader.live.killswitch import KillSwitch


def _tmp_path() -> str:
    """Return a unique temp file path that does NOT exist yet."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)   # remove so KillSwitch starts with no file
    return path


# ---------------------------------------------------------------------------
# Basic trip / is_active / reason
# ---------------------------------------------------------------------------

def test_trip_makes_active():
    path = _tmp_path()
    try:
        ks = KillSwitch(path=path)
        assert not ks.is_active()

        ks.trip(reason="Drawdown exceeded 5%", source="operator")

        assert ks.is_active()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_trip_persists_reason():
    path = _tmp_path()
    try:
        ks = KillSwitch(path=path)
        ks.trip(reason="Manual halt", source="monitor")

        status = ks.status()
        assert status["active"] is True
        assert status["reason"] == "Manual halt"
        assert status["source"] == "monitor"
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_clear_deactivates():
    path = _tmp_path()
    try:
        ks = KillSwitch(path=path)
        ks.trip(reason="Test", source="test")
        assert ks.is_active()

        ks.clear()

        assert not ks.is_active()
    finally:
        if os.path.exists(path):
            os.unlink(path)


# ---------------------------------------------------------------------------
# Disk persistence (survives new instance)
# ---------------------------------------------------------------------------

def test_survives_new_instance():
    """A new KillSwitch object on the same path reads state from disk."""
    path = _tmp_path()
    try:
        ks1 = KillSwitch(path=path)
        ks1.trip(reason="Persistent reason", source="automated")

        # Brand-new instance — no in-memory state
        ks2 = KillSwitch(path=path)
        assert ks2.is_active()
        assert ks2.status()["reason"] == "Persistent reason"
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_clear_survives_new_instance():
    """clear() on one instance means a new instance sees it as inactive."""
    path = _tmp_path()
    try:
        ks1 = KillSwitch(path=path)
        ks1.trip(reason="x", source="y")
        ks1.clear()

        ks2 = KillSwitch(path=path)
        assert not ks2.is_active()
    finally:
        if os.path.exists(path):
            os.unlink(path)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_inactive_when_no_file():
    path = _tmp_path()
    # File does not exist
    ks = KillSwitch(path=path)
    assert not ks.is_active()
    assert ks.status() == {}


def test_clear_is_safe_when_not_active():
    """clear() should not raise if the file doesn't exist."""
    path = _tmp_path()
    ks = KillSwitch(path=path)
    ks.clear()  # should not raise
    assert not ks.is_active()


def test_trip_with_optional_ts():
    """trip() with ts param stores it in the status dict."""
    path = _tmp_path()
    try:
        ks = KillSwitch(path=path)
        ks.trip(reason="Test ts", source="test", ts="2026-06-16T00:00:00Z")

        status = ks.status()
        assert status.get("ts") == "2026-06-16T00:00:00Z"
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_trip_without_ts_omits_key():
    """trip() without ts should NOT include a 'ts' key (determinism)."""
    path = _tmp_path()
    try:
        ks = KillSwitch(path=path)
        ks.trip(reason="no ts", source="test")

        status = ks.status()
        assert "ts" not in status
    finally:
        if os.path.exists(path):
            os.unlink(path)
