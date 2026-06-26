# trader/research/holdout_gate.py
"""RESEARCH ONLY — enforce the "open the holdout exactly once" discipline.

A locked-holdout test is only meaningful if you commit to ONE pre-registered
evaluation spec before looking.  This module makes the holdout impossible to
open unless the submitted spec hash exactly matches a single pre-registered
spec — so you cannot fish across signals/horizons on the holdout.

Mechanism (Codex-recommended; a lock file or editable flag alone is theatre):
  1. ``spec_hash(spec)``     — stable SHA-256 of the full evaluation spec
                               (signal id, markets, horizon, params, universe…).
  2. ``preregister(spec)``   — write the ONE approved hash to a sentinel file.
                               Refuses to overwrite a different existing hash.
  3. ``assert_holdout_allowed(spec)`` — raises unless the spec hash matches the
                               pre-registered one; appends every attempt to an
                               append-only audit registry.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

PREREGISTRATION_PATH = "experiments/holdout_preregistration.json"
REGISTRY_PATH = "experiments/holdout_registry.jsonl"


class HoldoutViolation(RuntimeError):
    """Raised when a holdout evaluation is attempted without an exact match to
    the single pre-registered spec."""


def spec_hash(spec: dict[str, Any]) -> str:
    """Stable SHA-256 of an evaluation spec (order-insensitive on dict keys)."""
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def preregister(
    spec: dict[str, Any],
    *,
    created_ts: str,
    path: str = PREREGISTRATION_PATH,
) -> str:
    """Pre-register the ONE spec allowed to touch the holdout.

    Returns the spec hash.  Refuses (ValueError) if a DIFFERENT spec is already
    registered — pre-registration is a one-time commitment.  Re-registering the
    identical spec is idempotent.
    """
    h = spec_hash(spec)
    if os.path.exists(path):
        existing = json.load(open(path, encoding="utf-8"))
        if existing.get("spec_hash") != h:
            raise ValueError(
                f"A different holdout spec is already pre-registered "
                f"({existing.get('spec_hash')[:12]}…). Pre-registration is a "
                "one-time commitment — delete the sentinel only with intent."
            )
        return h
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"spec_hash": h, "spec": spec, "created_ts": created_ts}, fh, indent=2)
    return h


def assert_holdout_allowed(
    spec: dict[str, Any],
    *,
    created_ts: str,
    preregistration_path: str = PREREGISTRATION_PATH,
    registry_path: str = REGISTRY_PATH,
) -> str:
    """Raise HoldoutViolation unless *spec* matches the pre-registered hash.

    Every attempt (allowed or not) is appended to the audit registry.  Returns
    the spec hash on success.
    """
    h = spec_hash(spec)
    allowed = False
    reason = ""
    if not os.path.exists(preregistration_path):
        reason = "no pre-registration exists"
    else:
        pre = json.load(open(preregistration_path, encoding="utf-8"))
        if pre.get("spec_hash") == h:
            allowed = True
        else:
            reason = f"spec hash {h[:12]}… != pre-registered {pre.get('spec_hash','')[:12]}…"

    os.makedirs(os.path.dirname(registry_path) or ".", exist_ok=True)
    with open(registry_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "created_ts": created_ts, "spec_hash": h,
            "allowed": allowed, "reason": reason,
        }, ensure_ascii=False) + "\n")

    if not allowed:
        raise HoldoutViolation(
            f"Holdout evaluation refused — {reason}. Pre-register this exact "
            "spec first (and only this one) before opening the holdout."
        )
    return h
