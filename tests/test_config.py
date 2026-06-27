# tests/test_config.py
"""Tests for AppConfig.from_env validation."""
from __future__ import annotations

import pytest

from trader.app.config import AppConfig, ConfigError

_FULL = {"KIS_APP_KEY": "k", "KIS_APP_SECRET": "s", "KIS_ACCOUNT": "123-45"}


def _set(monkeypatch, env: dict):
    for var in ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ACCOUNT", "KIS_PAPER"):
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_valid_config_defaults_to_paper(monkeypatch):
    _set(monkeypatch, _FULL)
    cfg = AppConfig.from_env()
    assert cfg.kis_app_key == "k"
    assert cfg.paper is True            # default safe


def test_missing_key_raises(monkeypatch):
    _set(monkeypatch, {"KIS_APP_SECRET": "s", "KIS_ACCOUNT": "1"})
    with pytest.raises(ConfigError, match="KIS_APP_KEY"):
        AppConfig.from_env()


def test_empty_key_raises(monkeypatch):
    _set(monkeypatch, {**_FULL, "KIS_APP_KEY": "   "})
    with pytest.raises(ConfigError, match="KIS_APP_KEY"):
        AppConfig.from_env()


def test_all_missing_lists_all(monkeypatch):
    _set(monkeypatch, {})
    with pytest.raises(ConfigError) as ei:
        AppConfig.from_env()
    msg = str(ei.value)
    assert "KIS_APP_KEY" in msg and "KIS_APP_SECRET" in msg and "KIS_ACCOUNT" in msg


def test_paper_only_disabled_by_exact_zero(monkeypatch):
    _set(monkeypatch, {**_FULL, "KIS_PAPER": "0"})
    assert AppConfig.from_env().paper is False
    _set(monkeypatch, {**_FULL, "KIS_PAPER": "false"})
    assert AppConfig.from_env().paper is True   # only "0" disables → stays paper-safe


def test_values_are_stripped(monkeypatch):
    _set(monkeypatch, {"KIS_APP_KEY": " k ", "KIS_APP_SECRET": " s ", "KIS_ACCOUNT": " a "})
    cfg = AppConfig.from_env()
    assert cfg.kis_app_key == "k" and cfg.kis_account == "a"
