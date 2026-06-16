# tests/test_experiment_log.py
"""Tests for trader/research/experiment_log.py (P1 multiple-testing discipline)."""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

import pytest

from trader.research.experiment_log import (
    ExperimentLog,
    ExperimentRecord,
    multiple_testing_warning,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rec(
    *,
    kind: str = "evaluate",
    strategy: str = "my_strategy",
    experiment_id: str | None = None,
    metrics: dict | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id or str(uuid.uuid4()),
        created_ts="2026-06-17T00:00:00Z",
        kind=kind,
        strategy=strategy,
        params={"lookback": 252},
        universe=["AAPL", "MSFT"],
        date_start="2020-01-01",
        date_end="2024-12-31",
        dataset_manifest_id="sha256:abc123",
        code_commit="deadbeef",
        metrics=metrics or {"sharpe": 0.5},
    )


# ---------------------------------------------------------------------------
# ExperimentRecord
# ---------------------------------------------------------------------------

class TestExperimentRecord:
    def test_frozen(self):
        r = _rec()
        with pytest.raises((AttributeError, TypeError)):
            r.kind = "other"  # type: ignore[misc]

    def test_round_trip_dict(self):
        r = _rec()
        d = r.to_dict()
        r2 = ExperimentRecord.from_dict(d)
        assert r == r2

    def test_notes_default_empty(self):
        r = _rec()
        assert r.notes == ""

    def test_notes_explicit(self):
        r = ExperimentRecord(
            experiment_id="x",
            created_ts="2026-06-17T00:00:00Z",
            kind="evaluate",
            strategy="s",
            params={},
            universe=[],
            date_start="2020-01-01",
            date_end="2020-12-31",
            dataset_manifest_id=None,
            code_commit=None,
            metrics={},
            notes="pre-registered run",
        )
        assert r.notes == "pre-registered run"

    def test_optional_fields_none(self):
        r = ExperimentRecord(
            experiment_id="x",
            created_ts="2026-06-17T00:00:00Z",
            kind="evaluate",
            strategy="s",
            params={},
            universe=[],
            date_start="2020-01-01",
            date_end="2020-12-31",
            dataset_manifest_id=None,
            code_commit=None,
            metrics={},
        )
        assert r.dataset_manifest_id is None
        assert r.code_commit is None


# ---------------------------------------------------------------------------
# ExperimentLog — append / all / persistence
# ---------------------------------------------------------------------------

class TestExperimentLogAppendAll:
    def test_all_empty_when_no_file(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        assert log.all() == []

    def test_append_and_all(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        r = _rec()
        log.append(r)
        rows = log.all()
        assert len(rows) == 1
        assert rows[0]["experiment_id"] == r.experiment_id
        assert rows[0]["kind"] == "evaluate"

    def test_multiple_appends_preserve_order(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        ids = [str(i) for i in range(5)]
        for i in ids:
            log.append(_rec(experiment_id=i))
        rows = log.all()
        assert [r["experiment_id"] for r in rows] == ids

    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / "log.jsonl"
        log1 = ExperimentLog(path)
        log1.append(_rec(experiment_id="first"))

        log2 = ExperimentLog(path)
        log2.append(_rec(experiment_id="second"))

        log3 = ExperimentLog(path)
        rows = log3.all()
        assert len(rows) == 2
        assert rows[0]["experiment_id"] == "first"
        assert rows[1]["experiment_id"] == "second"

    def test_file_is_valid_jsonl(self, tmp_path):
        path = tmp_path / "log.jsonl"
        log = ExperimentLog(path)
        log.append(_rec(experiment_id="a"))
        log.append(_rec(experiment_id="b"))

        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "experiment_id" in obj

    def test_parent_dir_created(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "log.jsonl"
        log = ExperimentLog(nested)
        log.append(_rec())
        assert nested.exists()

    def test_all_returns_dicts_not_records(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        log.append(_rec())
        rows = log.all()
        assert isinstance(rows[0], dict)

    def test_metrics_round_trip(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        metrics = {"sharpe": 1.23, "cagr": 0.15, "max_dd": -0.12}
        log.append(_rec(metrics=metrics))
        row = log.all()[0]
        assert row["metrics"] == metrics


# ---------------------------------------------------------------------------
# ExperimentLog — trial_count
# ---------------------------------------------------------------------------

class TestTrialCount:
    def test_zero_when_empty(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        assert log.trial_count() == 0

    def test_counts_all_when_no_filter(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        for _ in range(7):
            log.append(_rec())
        assert log.trial_count() == 7

    def test_filter_by_kind(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        for _ in range(3):
            log.append(_rec(kind="evaluate"))
        for _ in range(5):
            log.append(_rec(kind="momentum"))
        assert log.trial_count(kind="evaluate") == 3
        assert log.trial_count(kind="momentum") == 5

    def test_filter_by_strategy(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        for _ in range(4):
            log.append(_rec(strategy="strat_A"))
        for _ in range(2):
            log.append(_rec(strategy="strat_B"))
        assert log.trial_count(strategy="strat_A") == 4
        assert log.trial_count(strategy="strat_B") == 2

    def test_filter_kind_and_strategy_anded(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        log.append(_rec(kind="evaluate",  strategy="strat_A"))
        log.append(_rec(kind="momentum",  strategy="strat_A"))
        log.append(_rec(kind="evaluate",  strategy="strat_B"))
        log.append(_rec(kind="evaluate",  strategy="strat_A"))
        # only evaluate + strat_A
        assert log.trial_count(kind="evaluate", strategy="strat_A") == 2
        # evaluate only (both strat_A and strat_B)
        assert log.trial_count(kind="evaluate") == 3

    def test_no_match_returns_zero(self, tmp_path):
        log = ExperimentLog(tmp_path / "log.jsonl")
        log.append(_rec(kind="evaluate"))
        assert log.trial_count(kind="momentum") == 0
        assert log.trial_count(strategy="nonexistent") == 0


# ---------------------------------------------------------------------------
# multiple_testing_warning
# ---------------------------------------------------------------------------

class TestMultipleTestingWarning:
    def test_zero_trials_empty(self):
        assert multiple_testing_warning(0) == ""

    def test_negative_trials_empty(self):
        assert multiple_testing_warning(-1) == ""

    def test_one_trial_mild(self):
        msg = multiple_testing_warning(1)
        assert "1 trial" in msg
        # No strong warning for n=1
        assert "⚠️" not in msg or "overfit" not in msg

    def test_few_trials_no_strong_warning(self):
        for n in [2, 3, 4]:
            msg = multiple_testing_warning(n)
            assert str(n) in msg
            assert "overfit" not in msg

    def test_five_to_nine_moderate_warning(self):
        for n in [5, 6, 7, 8, 9]:
            msg = multiple_testing_warning(n)
            assert "⚠️" in msg
            assert str(n) in msg
            # Expected best-of-n Sharpe should be present
            expected = math.sqrt(2.0 * math.log(n))
            # Check the rounded value appears somewhere in the message
            assert f"{expected:.2f}" in msg

    def test_ten_plus_strong_warning(self):
        for n in [10, 15, 20, 50, 100]:
            msg = multiple_testing_warning(n)
            assert "⚠️" in msg
            assert "overfit" in msg or "likely overfit" in msg
            assert str(n) in msg

    def test_ten_contains_expected_best_sharpe(self):
        msg = multiple_testing_warning(10)
        expected = math.sqrt(2.0 * math.log(10))
        assert f"{expected:.2f}" in msg

    def test_warning_mentions_sqrt_2_ln_n_rule(self):
        msg = multiple_testing_warning(10)
        # The mathematical rule should be documented in the message
        assert "sqrt" in msg or "ln" in msg or "√" in msg

    def test_warning_mentions_holdout(self):
        msg = multiple_testing_warning(20)
        assert "holdout" in msg.lower()

    def test_escalation_low_to_high(self):
        # Higher n → longer / more serious warning
        msg_low  = multiple_testing_warning(2)
        msg_high = multiple_testing_warning(50)
        assert len(msg_high) > len(msg_low)

    def test_pre_register_mentioned_at_low_n(self):
        msg = multiple_testing_warning(1)
        assert "pre-register" in msg.lower() or "pre-reg" in msg.lower()

    def test_large_n_mentions_trial_count(self):
        msg = multiple_testing_warning(100)
        assert "100" in msg


# ---------------------------------------------------------------------------
# Integration: wiring into evaluate()
# ---------------------------------------------------------------------------

class TestEvaluateWiring:
    def test_no_log_returns_no_warning(self):
        """evaluate() without experiment_log should not include warning keys."""
        from datetime import datetime, timedelta, timezone
        from trader.backtest.evaluate import evaluate
        from trader.core.events import BarEvent, Market, Symbol

        sym = Symbol("AAPL", Market.NASDAQ, "USD")
        t0  = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bars = [BarEvent(sym, t0 + timedelta(days=i), 100+i, 101+i, 99+i, 100+i, 1000)
                for i in range(60)]

        result = evaluate(bars)
        assert "multiple_testing_warning" not in result
        assert "trial_count" not in result

    def test_with_log_appends_and_returns_warning(self, tmp_path):
        """evaluate() with experiment_log should append, return trial_count, warning."""
        from datetime import datetime, timedelta, timezone
        from trader.backtest.evaluate import evaluate
        from trader.core.events import BarEvent, Market, Symbol

        sym = Symbol("AAPL", Market.NASDAQ, "USD")
        t0  = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bars = [BarEvent(sym, t0 + timedelta(days=i), 100+i, 101+i, 99+i, 100+i, 1000)
                for i in range(60)]

        log = ExperimentLog(tmp_path / "log.jsonl")
        result = evaluate(bars, experiment_log=log, created_ts="2026-06-17T00:00:00Z")

        assert result["trial_count"] == 1
        assert "multiple_testing_warning" in result
        # 1 trial → mild or informational message
        assert isinstance(result["multiple_testing_warning"], str)
        assert log.trial_count(kind="evaluate") == 1

    def test_with_log_format_report_includes_warning_at_high_n(self, tmp_path):
        """format_report should include the warning section when trial_count is high."""
        from datetime import datetime, timedelta, timezone
        from trader.backtest.evaluate import evaluate, format_report
        from trader.core.events import BarEvent, Market, Symbol

        sym = Symbol("AAPL", Market.NASDAQ, "USD")
        t0  = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bars = [BarEvent(sym, t0 + timedelta(days=i), 100+i, 101+i, 99+i, 100+i, 1000)
                for i in range(60)]

        log = ExperimentLog(tmp_path / "log.jsonl")
        # Pre-populate with 9 prior runs so 10th triggers strong warning
        for _ in range(9):
            log.append(_rec(kind="evaluate", strategy="evaluate"))

        result = evaluate(bars, experiment_log=log, created_ts="2026-06-17T00:00:00Z")
        assert result["trial_count"] == 10

        report = format_report(result)
        assert "MULTIPLE-TESTING WARNING" in report
        assert "overfit" in report.lower()
