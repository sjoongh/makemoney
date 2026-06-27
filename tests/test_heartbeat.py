# tests/test_heartbeat.py
"""Tests for the heartbeat / dead-man's switch — pure, clock-injected."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

from trader.live import heartbeat as hb

_NOW = datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc)


def _path():
    return os.path.join(tempfile.mkdtemp(), ".heartbeat.json")


def test_record_then_load():
    p = _path()
    hb.record("daily_us", ts=_NOW.isoformat(), path=p)
    assert hb.load(p)["daily_us"] == _NOW.isoformat()


def test_record_updates_existing():
    p = _path()
    hb.record("daily_us", ts=(_NOW - timedelta(days=1)).isoformat(), path=p)
    hb.record("daily_us", ts=_NOW.isoformat(), path=p)
    assert hb.load(p)["daily_us"] == _NOW.isoformat()


def test_record_keeps_other_components():
    p = _path()
    hb.record("daily_us", ts=_NOW.isoformat(), path=p)
    hb.record("forward", ts=_NOW.isoformat(), path=p)
    state = hb.load(p)
    assert set(state) == {"daily_us", "forward"}


def test_check_missing_is_stale():
    p = _path()
    stale = hb.check(_NOW, {"daily_us": 26.0}, path=p)
    assert len(stale) == 1
    assert stale[0]["reason"] == "never recorded"


def test_check_old_is_stale():
    p = _path()
    hb.record("daily_us", ts=(_NOW - timedelta(hours=30)).isoformat(), path=p)
    stale = hb.check(_NOW, {"daily_us": 26.0}, path=p)
    assert len(stale) == 1
    assert stale[0]["reason"] == "stale"
    assert stale[0]["age_hours"] == 30.0


def test_check_fresh_is_ok():
    p = _path()
    hb.record("daily_us", ts=(_NOW - timedelta(hours=2)).isoformat(), path=p)
    assert hb.check(_NOW, {"daily_us": 26.0}, path=p) == []


def test_check_unparseable_timestamp():
    p = _path()
    hb.record("daily_us", ts="not-a-date", path=p)
    stale = hb.check(_NOW, {"daily_us": 26.0}, path=p)
    assert stale[0]["reason"] == "unparseable timestamp"


def test_load_missing_file_returns_empty():
    assert hb.load(_path()) == {}
