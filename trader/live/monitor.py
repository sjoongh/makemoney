# trader/live/monitor.py
"""Alert monitoring layer (P0 safety).

Provides a fan-out Monitor that emits structured alerts to one or more
AlertSink implementations.

Severities (ordered low → high): INFO / WARN / CRITICAL

AlertSink Protocol — any object with::

    def emit(self, severity: str, event: str, detail: dict) -> None: ...

Built-in sinks:
  LogAlertSink   — emits to Python logging (always).
  WebhookAlertSink — POSTs JSON payload for WARN and CRITICAL only.
"""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Severity ordering — used to filter (WARN+ only for webhook, etc.)
_SEVERITY_RANK: dict[str, int] = {
    "INFO": 0,
    "WARN": 1,
    "CRITICAL": 2,
}


# ---------------------------------------------------------------------------
# AlertSink Protocol (structural typing — no runtime dependency on Protocol)
# ---------------------------------------------------------------------------

class AlertSink:
    """Protocol-style base class.  Subclass or duck-type."""

    def emit(self, severity: str, event: str, detail: dict) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# LogAlertSink
# ---------------------------------------------------------------------------

class LogAlertSink:
    """Emits alerts to Python ``logging``.

    INFO  → logger.info
    WARN  → logger.warning
    CRITICAL → logger.critical
    """

    def emit(self, severity: str, event: str, detail: dict) -> None:
        msg = "[ALERT][%s] %s — %s"
        if severity == "CRITICAL":
            logger.critical(msg, severity, event, detail)
        elif severity == "WARN":
            logger.warning(msg, severity, event, detail)
        else:
            logger.info(msg, severity, event, detail)


# ---------------------------------------------------------------------------
# WebhookAlertSink
# ---------------------------------------------------------------------------

class WebhookAlertSink:
    """POSTs JSON alert payload to a webhook URL for WARN and CRITICAL only.

    INFO alerts are silently dropped (noise filter for webhooks).

    Args:
        url: The HTTP/HTTPS endpoint to POST to.
        post: Injectable callable matching ``requests.post`` signature
              (for testing without real HTTP).  Defaults to using the
              built-in ``urllib.request`` so no extra dependency is required.
    """

    def __init__(self, url: str, post: Optional[Callable] = None) -> None:
        self._url = url
        self._post = post  # injectable; None → use urllib

    def emit(self, severity: str, event: str, detail: dict) -> None:
        # Only post WARN and above
        if _SEVERITY_RANK.get(severity, 0) < _SEVERITY_RANK["WARN"]:
            return

        payload = {"severity": severity, "event": event, "detail": detail}

        if self._post is not None:
            self._post(self._url, json=payload)
        else:
            import urllib.request as _req
            data = json.dumps(payload).encode()
            req = _req.Request(
                self._url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with _req.urlopen(req, timeout=5):
                    pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("WebhookAlertSink: POST to %s failed: %s", self._url, exc)


# ---------------------------------------------------------------------------
# Monitor — fan-out to all sinks
# ---------------------------------------------------------------------------

class Monitor:
    """Holds a list of AlertSinks and fans out alert() calls to all of them.

    Args:
        sinks: List of objects implementing ``emit(severity, event, detail)``.
    """

    def __init__(self, sinks: list) -> None:
        self._sinks = list(sinks)

    def alert(self, severity: str, event: str, detail: dict) -> None:
        """Emit an alert to all registered sinks.

        Args:
            severity: "INFO", "WARN", or "CRITICAL".
            event: Short snake_case event code (e.g. "ORDER_REJECTED").
            detail: Free-form dict with context (ticker, reason, etc.).
        """
        for sink in self._sinks:
            try:
                sink.emit(severity, event, detail)
            except Exception as exc:  # noqa: BLE001
                # Alert sink failures must never crash the trading engine
                logger.warning("Monitor: sink %r raised during emit: %s", sink, exc)
