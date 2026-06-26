# tests/test_holdout_gate.py
"""Tests for the holdout-once gate — RESEARCH ONLY."""
from __future__ import annotations

import os
import tempfile

import pytest

from trader.research.holdout_gate import (
    HoldoutViolation,
    assert_holdout_allowed,
    preregister,
    spec_hash,
)

_TS = "2026-06-24T00:00:00+00:00"


def _paths():
    d = tempfile.mkdtemp()
    return os.path.join(d, "prereg.json"), os.path.join(d, "registry.jsonl")


def test_spec_hash_is_order_insensitive():
    a = {"signal": "mom", "markets": ["US", "KR"], "horizon": 21}
    b = {"horizon": 21, "markets": ["US", "KR"], "signal": "mom"}
    assert spec_hash(a) == spec_hash(b)


def test_spec_hash_changes_with_content():
    a = {"signal": "mom", "horizon": 21}
    b = {"signal": "mom", "horizon": 5}
    assert spec_hash(a) != spec_hash(b)


def test_preregister_then_allowed():
    pre, reg = _paths()
    spec = {"signal": "momentum_12_1", "markets": ["US"], "horizon": 21}
    preregister(spec, created_ts=_TS, path=pre)
    # exact match is allowed
    h = assert_holdout_allowed(spec, created_ts=_TS,
                               preregistration_path=pre, registry_path=reg)
    assert h == spec_hash(spec)
    assert os.path.exists(reg)


def test_unregistered_spec_refused():
    pre, reg = _paths()
    preregister({"signal": "momentum_12_1", "horizon": 21}, created_ts=_TS, path=pre)
    with pytest.raises(HoldoutViolation):
        assert_holdout_allowed({"signal": "reversal", "horizon": 5}, created_ts=_TS,
                               preregistration_path=pre, registry_path=reg)
    # the refused attempt is still audited
    assert "allowed" in open(reg).read()


def test_no_preregistration_refused():
    pre, reg = _paths()
    with pytest.raises(HoldoutViolation):
        assert_holdout_allowed({"signal": "x"}, created_ts=_TS,
                               preregistration_path=pre, registry_path=reg)


def test_cannot_preregister_a_second_different_spec():
    pre, reg = _paths()
    preregister({"signal": "a", "horizon": 21}, created_ts=_TS, path=pre)
    with pytest.raises(ValueError):
        preregister({"signal": "b", "horizon": 21}, created_ts=_TS, path=pre)
    # re-registering the identical spec is idempotent
    assert preregister({"signal": "a", "horizon": 21}, created_ts=_TS, path=pre)


def test_registry_is_append_only_audit():
    pre, reg = _paths()
    spec = {"signal": "a", "horizon": 21}
    preregister(spec, created_ts=_TS, path=pre)
    assert_holdout_allowed(spec, created_ts=_TS, preregistration_path=pre, registry_path=reg)
    assert_holdout_allowed(spec, created_ts=_TS, preregistration_path=pre, registry_path=reg)
    assert len(open(reg).read().strip().splitlines()) == 2
