# tests/test_monitoring_hardening.py
"""Monitoring hardening: external dead-man ping + error-gated heartbeats."""
from __future__ import annotations

from trader.app import run_healthcheck as H


def test_external_ping_healthy_hits_base_url(monkeypatch):
    calls = []
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda url, timeout=5.0: calls.append(url))
    H._external_ping(True, "https://hc-ping.example/abc")
    assert calls == ["https://hc-ping.example/abc"]


def test_external_ping_stale_hits_fail_endpoint(monkeypatch):
    calls = []
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda url, timeout=5.0: calls.append(url))
    H._external_ping(False, "https://hc-ping.example/abc/")
    assert calls == ["https://hc-ping.example/abc/fail"]


def test_external_ping_no_url_is_noop(monkeypatch):
    calls = []
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda url, timeout=5.0: calls.append(url))
    H._external_ping(True, None)
    assert calls == []


def test_external_ping_swallows_network_error(monkeypatch):
    def boom(url, timeout=5.0):
        raise OSError("network down")
    monkeypatch.setattr("urllib.request.urlopen", boom)
    H._external_ping(True, "https://hc-ping.example/abc")  # must not raise


# ── error-gated heartbeats (pure logic mirrors the runner gates) ───────────

def test_accumulate_total_failure_detection():
    # attempted>0 and fetched==0 → total failure (skip heartbeat)
    def total_failure(s):
        attempted = s["fetched"] + s["errored"] + s["cooled"]
        return attempted > 0 and s["fetched"] == 0
    assert total_failure({"fetched": 0, "errored": 5, "cooled": 0})
    assert not total_failure({"fetched": 3, "errored": 2, "cooled": 0})
    assert not total_failure({"fetched": 0, "errored": 0, "cooled": 0})  # nothing attempted


def test_forward_total_failure_detection():
    def total_failure(s):
        return s["symbols"] > 0 and s["errors"] >= s["symbols"]
    assert total_failure({"symbols": 10, "errors": 10})
    assert not total_failure({"symbols": 10, "errors": 0, })       # weekend: 0 err
    assert not total_failure({"symbols": 0, "errors": 0})
