# trader/live/heartbeat.py
"""Heartbeat / dead-man's switch for scheduled jobs.

The #1 silent-failure mode for an unattended retail deployment is a scheduled
run that simply never fires (laptop asleep, cron disabled, machine off) — no
error, no alert, just nothing. This records a timestamp on each *successful*
run and lets a healthcheck detect staleness and alert.

Pure and clock-injectable (no wall-clock inside) so it is fully testable.
NEVER used to place orders — observability only.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from typing import Optional

DEFAULT_PATH = ".heartbeat.json"


def record(component: str, *, ts: str, path: str = DEFAULT_PATH) -> None:
    """Record a successful run of *component* at ISO timestamp *ts* (atomic)."""
    state = load(path)
    state[component] = ts
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load(path: str = DEFAULT_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def check(
    now: datetime,
    expectations: dict[str, float],
    *,
    path: str = DEFAULT_PATH,
) -> list[dict]:
    """Return a list of STALE components.

    Args:
        now:          current datetime (timezone-aware), injected.
        expectations: {component: max_age_hours}. A component older than its
                      max age (or never recorded) is stale.
        path:         heartbeat file.

    Each stale entry: {component, last, age_hours, max_age_hours, reason}.
    """
    state = load(path)
    stale: list[dict] = []
    for component, max_age_h in expectations.items():
        last = state.get(component)
        if last is None:
            stale.append({
                "component": component, "last": None,
                "age_hours": None, "max_age_hours": max_age_h,
                "reason": "never recorded",
            })
            continue
        try:
            last_dt = datetime.fromisoformat(last)
        except ValueError:
            stale.append({
                "component": component, "last": last,
                "age_hours": None, "max_age_hours": max_age_h,
                "reason": "unparseable timestamp",
            })
            continue
        age_h = (now - last_dt).total_seconds() / 3600.0
        if age_h > max_age_h:
            stale.append({
                "component": component, "last": last,
                "age_hours": round(age_h, 1), "max_age_hours": max_age_h,
                "reason": "stale",
            })
    return stale
