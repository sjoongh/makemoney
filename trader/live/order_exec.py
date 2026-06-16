# trader/live/order_exec.py
"""Resilient order submission layer (P0 safety).

Wraps KisClient.submit_order with:
  - Error classification (TRANSIENT / TERMINAL / UNKNOWN)
  - Exponential-backoff retry for transient errors only
  - No blind resubmit on UNKNOWN (caller must reconcile via fills)

Design constraints:
  - Deterministic: retry count/decision is deterministic; only wall-clock sleep
    varies and is injectable so tests run with zero real delay.
  - Pure logic: no strategy / indicator state touched here.
"""
from __future__ import annotations

import time as _time_module
from typing import Optional


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

_TRANSIENT_MARKERS = (
    "초당 거래건수",
    "EGW00201",
    "일시",
    "timeout",
    "잠시 후",
)

_TERMINAL_MARKERS = (
    "해당업무 미제공",
    "장시작전",
    "장종료",
    "수량",
    "잔고",
    "매수가능",
    "거부",
)


def classify_kis_error(msg: str) -> str:
    """Classify a KIS error message string.

    Returns:
        "TRANSIENT" — rate-limit / timeout; safe to retry.
        "TERMINAL"  — business reject; must NOT retry.
        "UNKNOWN"   — unrecognised; do NOT blind-resubmit.
    """
    for marker in _TRANSIENT_MARKERS:
        if marker in msg:
            return "TRANSIENT"
    for marker in _TERMINAL_MARKERS:
        if marker in msg:
            return "TERMINAL"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Resilient submitter
# ---------------------------------------------------------------------------

class ResilientSubmitter:
    """Wraps a KisClient and adds retry/classification logic around submit_order.

    Args:
        kis_client: Any object with a ``submit_order`` method matching the
                    KisClient signature (duck-typed for testability).
        max_retries: Maximum number of retry attempts on TRANSIENT errors.
        base_backoff: Base seconds for exponential back-off:
                      sleep = base_backoff * 2**attempt (attempt 0-based).
        sleep: Injectable sleep callable (default: ``time.sleep``).
               Tests pass ``lambda _: None`` for zero-delay execution.
    """

    def __init__(
        self,
        kis_client,
        *,
        max_retries: int = 3,
        base_backoff: float = 0.5,
        sleep=_time_module.sleep,
    ) -> None:
        self._kis = kis_client
        self._max_retries = max_retries
        self._base_backoff = base_backoff
        self._sleep = sleep

    def submit(
        self,
        ticker: str,
        market: str,
        side: str,
        quantity: int,
        price: float,
        order_type: str,
    ) -> dict:
        """Submit an order with retry/classification logic.

        Returns a result dict::

            {
                "status":   "SUBMITTED" | "REJECTED" | "UNKNOWN",
                "odno":     str | None,   # broker order id (only on SUBMITTED)
                "attempts": int,          # total call attempts made
                "reason":   str,          # error message / empty on success
            }

        Status semantics:
          SUBMITTED — order accepted; ``odno`` is set.
          REJECTED  — TERMINAL business reject; no retry performed.
          UNKNOWN   — exhausted retries on TRANSIENT error, OR
                      unclassified error; caller must reconcile via fills.
        """
        attempts = 0
        last_reason = ""

        for attempt in range(self._max_retries + 1):
            try:
                odno = self._kis.submit_order(
                    ticker=ticker,
                    market=market,
                    side=side,
                    quantity=quantity,
                    price=price,
                    order_type=order_type,
                )
                return {
                    "status": "SUBMITTED",
                    "odno": odno,
                    "attempts": attempt + 1,
                    "reason": "",
                }
            except RuntimeError as exc:
                attempts = attempt + 1
                last_reason = str(exc)
                classification = classify_kis_error(last_reason)

                if classification == "TERMINAL":
                    # Business reject — never retry
                    return {
                        "status": "REJECTED",
                        "odno": None,
                        "attempts": attempts,
                        "reason": last_reason,
                    }

                if classification == "TRANSIENT":
                    if attempt < self._max_retries:
                        # Exponential back-off before next attempt
                        delay = self._base_backoff * (2 ** attempt)
                        self._sleep(delay)
                        continue
                    # Exhausted retries on transient — UNKNOWN (do not mark filled)
                    return {
                        "status": "UNKNOWN",
                        "odno": None,
                        "attempts": attempts,
                        "reason": last_reason,
                    }

                # UNKNOWN classification — do NOT blind-resubmit
                return {
                    "status": "UNKNOWN",
                    "odno": None,
                    "attempts": attempts,
                    "reason": last_reason,
                }

        # Should not be reached, but be explicit
        return {
            "status": "UNKNOWN",
            "odno": None,
            "attempts": attempts,
            "reason": last_reason,
        }
