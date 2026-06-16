# tests/test_run_daily_gate.py
"""Tests for the hard LIVE_TRADING_ENABLED gate in trader/app/run_daily.py.

The gate logic is extracted into the pure function ``live_allowed()``,
which takes args_live, env dict, account string, and killswitch_path.
These tests exercise the function without running main().
"""
from __future__ import annotations

import os
import tempfile

import pytest

from trader.app.run_daily import live_allowed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_ks_path() -> str:
    """Return a temp path for a kill-switch file that does NOT exist yet."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    return path


_GOOD_ENV = {
    "LIVE_TRADING_ENABLED": "true",
    "KIS_LIVE_ACCOUNT_ALLOWLIST": "12345678,99999999",
}
_GOOD_ACCOUNT = "12345678"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_all_conditions_met_allows_live():
    path = _tmp_ks_path()
    allowed, reason = live_allowed(
        args_live=True,
        env=_GOOD_ENV,
        account=_GOOD_ACCOUNT,
        killswitch_path=path,
    )
    assert allowed is True
    assert reason == ""


# ---------------------------------------------------------------------------
# --live not passed
# ---------------------------------------------------------------------------

def test_no_live_flag_is_dry_run():
    path = _tmp_ks_path()
    allowed, reason = live_allowed(
        args_live=False,
        env=_GOOD_ENV,
        account=_GOOD_ACCOUNT,
        killswitch_path=path,
    )
    assert allowed is False
    assert "dry-run" in reason.lower() or "--live" in reason


# ---------------------------------------------------------------------------
# Missing / wrong LIVE_TRADING_ENABLED
# ---------------------------------------------------------------------------

def test_missing_env_var_blocks():
    path = _tmp_ks_path()
    env = {
        "KIS_LIVE_ACCOUNT_ALLOWLIST": "12345678",
        # LIVE_TRADING_ENABLED absent
    }
    allowed, reason = live_allowed(
        args_live=True,
        env=env,
        account=_GOOD_ACCOUNT,
        killswitch_path=path,
    )
    assert allowed is False
    assert "LIVE_TRADING_ENABLED" in reason


def test_env_var_false_blocks():
    path = _tmp_ks_path()
    env = {
        "LIVE_TRADING_ENABLED": "false",
        "KIS_LIVE_ACCOUNT_ALLOWLIST": "12345678",
    }
    allowed, reason = live_allowed(
        args_live=True,
        env=env,
        account=_GOOD_ACCOUNT,
        killswitch_path=path,
    )
    assert allowed is False
    assert "LIVE_TRADING_ENABLED" in reason


def test_env_var_case_insensitive_true():
    """'TRUE' and 'True' should also be accepted."""
    path = _tmp_ks_path()
    for variant in ("TRUE", "True", "  true  "):
        allowed, reason = live_allowed(
            args_live=True,
            env={
                "LIVE_TRADING_ENABLED": variant,
                "KIS_LIVE_ACCOUNT_ALLOWLIST": _GOOD_ACCOUNT,
            },
            account=_GOOD_ACCOUNT,
            killswitch_path=path,
        )
        assert allowed is True, f"Expected allowed for variant {variant!r}, got reason={reason}"


# ---------------------------------------------------------------------------
# Account not in allowlist
# ---------------------------------------------------------------------------

def test_account_not_in_allowlist_blocks():
    path = _tmp_ks_path()
    env = {
        "LIVE_TRADING_ENABLED": "true",
        "KIS_LIVE_ACCOUNT_ALLOWLIST": "99999999,88888888",
    }
    allowed, reason = live_allowed(
        args_live=True,
        env=env,
        account="12345678",   # not in list
        killswitch_path=path,
    )
    assert allowed is False
    assert "allowlist" in reason.lower() or "KIS_LIVE_ACCOUNT_ALLOWLIST" in reason


def test_empty_allowlist_blocks():
    path = _tmp_ks_path()
    env = {
        "LIVE_TRADING_ENABLED": "true",
        "KIS_LIVE_ACCOUNT_ALLOWLIST": "",
    }
    allowed, reason = live_allowed(
        args_live=True,
        env=env,
        account=_GOOD_ACCOUNT,
        killswitch_path=path,
    )
    assert allowed is False
    assert "KIS_LIVE_ACCOUNT_ALLOWLIST" in reason or "allowlist" in reason.lower()


def test_missing_allowlist_env_blocks():
    path = _tmp_ks_path()
    env = {
        "LIVE_TRADING_ENABLED": "true",
        # KIS_LIVE_ACCOUNT_ALLOWLIST absent
    }
    allowed, reason = live_allowed(
        args_live=True,
        env=env,
        account=_GOOD_ACCOUNT,
        killswitch_path=path,
    )
    assert allowed is False


# ---------------------------------------------------------------------------
# Kill switch active
# ---------------------------------------------------------------------------

def test_kill_switch_active_blocks_live():
    """Kill switch active → blocked even if all other conditions are met."""
    import json
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump({"active": True, "reason": "Drawdown exceeded", "source": "operator"}, f)

        allowed, reason = live_allowed(
            args_live=True,
            env=_GOOD_ENV,
            account=_GOOD_ACCOUNT,
            killswitch_path=path,
        )
        assert allowed is False
        assert "kill switch" in reason.lower()
        assert "Drawdown exceeded" in reason
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_kill_switch_inactive_does_not_block():
    """Kill switch file absent → not blocked by kill switch."""
    path = _tmp_ks_path()   # file does not exist
    allowed, reason = live_allowed(
        args_live=True,
        env=_GOOD_ENV,
        account=_GOOD_ACCOUNT,
        killswitch_path=path,
    )
    assert allowed is True
