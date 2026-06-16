# tests/test_order_exec.py
"""Tests for trader/live/order_exec.py — resilient order submission."""
from __future__ import annotations

import pytest

from trader.live.order_exec import classify_kis_error, ResilientSubmitter


# ---------------------------------------------------------------------------
# classify_kis_error
# ---------------------------------------------------------------------------

class TestClassifyKisError:
    def test_transient_rate_limit_korean(self):
        assert classify_kis_error("초당 거래건수 초과입니다") == "TRANSIENT"

    def test_transient_egw_code(self):
        assert classify_kis_error("EGW00201 오류가 발생했습니다") == "TRANSIENT"

    def test_transient_ilsi(self):
        assert classify_kis_error("일시적인 오류입니다") == "TRANSIENT"

    def test_transient_timeout(self):
        assert classify_kis_error("Connection timeout occurred") == "TRANSIENT"

    def test_transient_jamsi(self):
        assert classify_kis_error("잠시 후 다시 시도하세요") == "TRANSIENT"

    def test_terminal_service_unavailable(self):
        assert classify_kis_error("해당업무 미제공") == "TERMINAL"

    def test_terminal_before_open(self):
        assert classify_kis_error("장시작전 주문 불가") == "TERMINAL"

    def test_terminal_after_close(self):
        assert classify_kis_error("장종료 후 주문 불가") == "TERMINAL"

    def test_terminal_quantity(self):
        assert classify_kis_error("수량이 올바르지 않습니다") == "TERMINAL"

    def test_terminal_balance(self):
        assert classify_kis_error("잔고 부족") == "TERMINAL"

    def test_terminal_buy_available(self):
        assert classify_kis_error("매수가능 수량 초과") == "TERMINAL"

    def test_terminal_reject(self):
        assert classify_kis_error("거부 처리되었습니다") == "TERMINAL"

    def test_unknown_empty(self):
        assert classify_kis_error("") == "UNKNOWN"

    def test_unknown_random_message(self):
        assert classify_kis_error("Something completely unexpected happened") == "UNKNOWN"

    def test_transient_takes_priority_over_unknown(self):
        # A message with a TRANSIENT marker somewhere in it
        assert classify_kis_error("System error: EGW00201") == "TRANSIENT"


# ---------------------------------------------------------------------------
# Fake KIS client helpers
# ---------------------------------------------------------------------------

class _AlwaysSucceedKis:
    """submit_order always returns a fixed ODNO."""
    def __init__(self, odno: str = "ORDER001"):
        self.calls = 0
        self._odno = odno

    def submit_order(self, **kwargs):
        self.calls += 1
        return self._odno


class _FailThenSucceedKis:
    """Raises RuntimeError for the first `fail_count` calls, then succeeds."""
    def __init__(self, fail_msgs: list[str], success_odno: str = "ORDER999"):
        self._fail_msgs = list(fail_msgs)
        self._success_odno = success_odno
        self.calls = 0

    def submit_order(self, **kwargs):
        self.calls += 1
        if self._fail_msgs:
            raise RuntimeError(self._fail_msgs.pop(0))
        return self._success_odno


class _AlwaysFailKis:
    """Always raises RuntimeError with the given message."""
    def __init__(self, msg: str):
        self._msg = msg
        self.calls = 0

    def submit_order(self, **kwargs):
        self.calls += 1
        raise RuntimeError(self._msg)


# ---------------------------------------------------------------------------
# ResilientSubmitter tests
# ---------------------------------------------------------------------------

_ORDER_KWARGS = dict(
    ticker="AAPL",
    market="NASDAQ",
    side="BUY",
    quantity=10,
    price=150.0,
    order_type="00",
)


def _no_sleep(delay):
    """No-op sleep for tests — ensures zero real delay."""
    pass


def test_success_no_retry():
    """Success on first attempt: status=SUBMITTED, attempts=1, no sleep called."""
    sleep_calls = []
    kis = _AlwaysSucceedKis(odno="ABC123")
    s = ResilientSubmitter(kis, sleep=lambda d: sleep_calls.append(d))

    result = s.submit(**_ORDER_KWARGS)

    assert result["status"] == "SUBMITTED"
    assert result["odno"] == "ABC123"
    assert result["attempts"] == 1
    assert result["reason"] == ""
    assert kis.calls == 1
    assert sleep_calls == []


def test_transient_then_success():
    """Transient error then success: retries and returns SUBMITTED."""
    sleep_calls = []
    kis = _FailThenSucceedKis(
        fail_msgs=["EGW00201 rate limit hit"],
        success_odno="OK001",
    )
    s = ResilientSubmitter(kis, max_retries=3, base_backoff=1.0,
                           sleep=lambda d: sleep_calls.append(d))

    result = s.submit(**_ORDER_KWARGS)

    assert result["status"] == "SUBMITTED"
    assert result["odno"] == "OK001"
    assert result["attempts"] == 2        # 1 fail + 1 success
    assert kis.calls == 2
    assert len(sleep_calls) == 1          # one backoff sleep
    assert sleep_calls[0] == 1.0         # base_backoff * 2**0


def test_persistent_transient_exhausts_retries():
    """All attempts transient: status=UNKNOWN after max_retries+1 calls."""
    sleep_calls = []
    max_retries = 3
    kis = _AlwaysFailKis("초당 거래건수 초과")
    s = ResilientSubmitter(kis, max_retries=max_retries, base_backoff=0.5,
                           sleep=lambda d: sleep_calls.append(d))

    result = s.submit(**_ORDER_KWARGS)

    assert result["status"] == "UNKNOWN"
    assert result["odno"] is None
    assert result["attempts"] == max_retries + 1   # 1 initial + 3 retries
    assert kis.calls == max_retries + 1
    # Sleep is called max_retries times (not after the final attempt)
    assert len(sleep_calls) == max_retries
    # Exponential backoff: 0.5*2**0, 0.5*2**1, 0.5*2**2
    assert sleep_calls == [0.5, 1.0, 2.0]


def test_terminal_rejected_immediately():
    """TERMINAL error: status=REJECTED immediately, no retry, no sleep."""
    sleep_calls = []
    kis = _AlwaysFailKis("장시작전 주문 불가")
    s = ResilientSubmitter(kis, max_retries=3, sleep=lambda d: sleep_calls.append(d))

    result = s.submit(**_ORDER_KWARGS)

    assert result["status"] == "REJECTED"
    assert result["odno"] is None
    assert result["attempts"] == 1        # no retry
    assert kis.calls == 1
    assert sleep_calls == []             # no sleep


def test_unknown_error_no_blind_resubmit():
    """UNKNOWN error: status=UNKNOWN, exactly 1 attempt, no retry."""
    sleep_calls = []
    kis = _AlwaysFailKis("Completely unexpected broker error XYZ")
    s = ResilientSubmitter(kis, max_retries=3, sleep=lambda d: sleep_calls.append(d))

    result = s.submit(**_ORDER_KWARGS)

    assert result["status"] == "UNKNOWN"
    assert result["odno"] is None
    assert result["attempts"] == 1        # no blind resubmit
    assert kis.calls == 1
    assert sleep_calls == []             # no sleep


def test_backoff_values_with_two_retries():
    """Verify exponential backoff sequence with base_backoff=2.0."""
    sleep_calls = []
    kis = _FailThenSucceedKis(
        fail_msgs=["잠시 후", "잠시 후"],
        success_odno="X",
    )
    s = ResilientSubmitter(kis, max_retries=3, base_backoff=2.0,
                           sleep=lambda d: sleep_calls.append(d))

    result = s.submit(**_ORDER_KWARGS)

    assert result["status"] == "SUBMITTED"
    assert result["attempts"] == 3
    assert sleep_calls == [2.0, 4.0]     # 2.0*2**0, 2.0*2**1
