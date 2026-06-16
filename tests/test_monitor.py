# tests/test_monitor.py
"""Unit tests for trader/live/monitor.py — alert fan-out layer."""
from __future__ import annotations

import logging

import pytest

from trader.live.monitor import LogAlertSink, Monitor, WebhookAlertSink


# ---------------------------------------------------------------------------
# LogAlertSink
# ---------------------------------------------------------------------------

class TestLogAlertSink:
    def test_emit_info(self, caplog):
        sink = LogAlertSink()
        with caplog.at_level(logging.INFO, logger="trader.live.monitor"):
            sink.emit("INFO", "RUN_START", {"mode": "dry_run"})
        assert any("RUN_START" in r.message for r in caplog.records)

    def test_emit_warn(self, caplog):
        sink = LogAlertSink()
        with caplog.at_level(logging.WARNING, logger="trader.live.monitor"):
            sink.emit("WARN", "ORDER_REJECTED", {"ticker": "AAPL"})
        assert any("ORDER_REJECTED" in r.message for r in caplog.records)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_emit_critical(self, caplog):
        sink = LogAlertSink()
        with caplog.at_level(logging.CRITICAL, logger="trader.live.monitor"):
            sink.emit("CRITICAL", "ORDER_UNKNOWN_STATE", {"ticker": "AAPL"})
        assert any("ORDER_UNKNOWN_STATE" in r.message for r in caplog.records)
        assert any(r.levelno == logging.CRITICAL for r in caplog.records)


# ---------------------------------------------------------------------------
# WebhookAlertSink
# ---------------------------------------------------------------------------

class TestWebhookAlertSink:
    def test_warn_posts_to_webhook(self):
        posted = []

        def fake_post(url, json=None):
            posted.append({"url": url, "json": json})

        sink = WebhookAlertSink(url="http://fake/alert", post=fake_post)
        sink.emit("WARN", "ORDER_REJECTED", {"ticker": "AAPL", "reason": "잔고 부족"})

        assert len(posted) == 1
        assert posted[0]["url"] == "http://fake/alert"
        assert posted[0]["json"]["severity"] == "WARN"
        assert posted[0]["json"]["event"] == "ORDER_REJECTED"
        assert posted[0]["json"]["detail"]["ticker"] == "AAPL"

    def test_critical_posts_to_webhook(self):
        posted = []

        def fake_post(url, json=None):
            posted.append({"url": url, "json": json})

        sink = WebhookAlertSink(url="http://fake/alert", post=fake_post)
        sink.emit("CRITICAL", "ORDER_UNKNOWN_STATE", {"ticker": "005930"})

        assert len(posted) == 1
        assert posted[0]["json"]["severity"] == "CRITICAL"

    def test_info_not_posted_to_webhook(self):
        posted = []

        def fake_post(url, json=None):
            posted.append({"url": url, "json": json})

        sink = WebhookAlertSink(url="http://fake/alert", post=fake_post)
        sink.emit("INFO", "RUN_START", {"mode": "live"})

        # INFO must be silently dropped — no HTTP call
        assert posted == [], "INFO alerts must not be POSTed to webhook"

    def test_multiple_calls_accumulate(self):
        posted = []

        def fake_post(url, json=None):
            posted.append(json)

        sink = WebhookAlertSink(url="http://fake/alert", post=fake_post)
        sink.emit("WARN", "EVENT_A", {})
        sink.emit("CRITICAL", "EVENT_B", {})
        sink.emit("INFO", "EVENT_C", {})  # should be dropped

        assert len(posted) == 2
        assert posted[0]["event"] == "EVENT_A"
        assert posted[1]["event"] == "EVENT_B"


# ---------------------------------------------------------------------------
# Monitor fan-out
# ---------------------------------------------------------------------------

class _CaptureSink:
    """Test sink that records all calls."""
    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []

    def emit(self, severity: str, event: str, detail: dict) -> None:
        self.calls.append((severity, event, detail))


class TestMonitor:
    def test_fan_out_to_all_sinks(self):
        sink1 = _CaptureSink()
        sink2 = _CaptureSink()
        mon = Monitor([sink1, sink2])

        mon.alert("WARN", "ORDER_REJECTED", {"ticker": "AAPL"})

        assert len(sink1.calls) == 1
        assert len(sink2.calls) == 1
        assert sink1.calls[0] == ("WARN", "ORDER_REJECTED", {"ticker": "AAPL"})
        assert sink2.calls[0] == ("WARN", "ORDER_REJECTED", {"ticker": "AAPL"})

    def test_fan_out_multiple_alerts(self):
        sink = _CaptureSink()
        mon = Monitor([sink])

        mon.alert("INFO", "RUN_START", {"mode": "live"})
        mon.alert("WARN", "GATE_BLOCK", {"ticker": "AAPL", "reason": "FAT_FINGER_QTY"})
        mon.alert("CRITICAL", "ORDER_UNKNOWN_STATE", {"ticker": "005930"})

        assert len(sink.calls) == 3
        assert sink.calls[0][0] == "INFO"
        assert sink.calls[1][0] == "WARN"
        assert sink.calls[2][0] == "CRITICAL"

    def test_sink_failure_does_not_crash_monitor(self):
        """A broken sink must not prevent other sinks from receiving alerts."""

        class BrokenSink:
            def emit(self, severity, event, detail):
                raise RuntimeError("sink is broken")

        good_sink = _CaptureSink()
        mon = Monitor([BrokenSink(), good_sink])

        # Must not raise
        mon.alert("WARN", "ORDER_REJECTED", {"ticker": "AAPL"})

        # Good sink still received the alert
        assert len(good_sink.calls) == 1

    def test_empty_sinks_list_is_valid(self):
        mon = Monitor([])
        # Must not raise
        mon.alert("CRITICAL", "ORDER_UNKNOWN_STATE", {})
