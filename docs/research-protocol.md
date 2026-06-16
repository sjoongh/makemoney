# Research Protocol — Multiple-Testing Discipline

## Why this exists

Every time you try a strategy, change a parameter, alter the universe, or shift
the lookback window, you run an implicit statistical test.  After **N** attempts,
the best result is NOT drawn from the distribution of "one honest test" — it is
drawn from the distribution of **the maximum of N tests**.

Under pure noise, the expected best Sharpe across N independent trials grows as
approximately **sqrt(2 ln N)**:

| N trials | Expected best Sharpe (noise) |
|----------|------------------------------|
| 1        | 0.00 (no selection)          |
| 5        | 1.79                         |
| 10       | 2.15                         |
| 20       | 2.45                         |
| 50       | 2.80                         |
| 100      | 3.03                         |

A "good" backtest Sharpe of 1.5 after 20 attempts would be expected under pure
noise **roughly half the time**.  This is why every experiment must be logged and
every result must be accompanied by a trial count.

---

## The Four-Step Protocol

### Step 1 — Pre-register

**Write down your hypothesis and primary metric BEFORE touching any data or code.**

- What is the signal you believe in?  Why?
- What is the primary performance metric (Sharpe? CAGR? Max drawdown)?
- What universe, lookback, and date range will you use?
- Record this in `experiments/log.jsonl` (via `ExperimentLog`) or a dated notes file.

Pre-registration locks in the number of "free" decisions made before the test.
Any decision made AFTER looking at results is not pre-registered and adds to
the trial count.

### Step 2 — Create splits once, upfront

Call `chronological_split()` **once**, immediately after pre-registration, and
**store the PeriodSplit**.  Do not change the splits later.

```python
from trader.research.splits import chronological_split

split = chronological_split(
    start_date="2015-01-01",
    end_date="2024-12-31",
    train=0.5,
    validation=0.25,
    holdout=0.25,
)
# Immediately note: holdout = [split.holdout_start, split.holdout_end]
# DO NOT LOOK AT HOLDOUT DATA until Step 5.
```

The holdout is **always the most recent slice**.  This mirrors real trading:
the future is the true out-of-sample period.

### Step 3 — Develop on TRAIN only

All exploratory work — signal definition, feature engineering, indicator
parameters — is done using only `filter_bars_to_window(bars, split.train_start,
split.train_end)`.

Every experiment is logged:

```python
from trader.research.experiment_log import ExperimentLog, ExperimentRecord

log = ExperimentLog()
log.append(ExperimentRecord(
    experiment_id="my_run_001",
    created_ts="2026-06-17T10:00:00Z",
    kind="momentum",
    strategy="cross_sectional_momentum",
    params={"lookback": 252, "skip": 21},
    universe=["AAPL", "MSFT"],
    date_start=split.train_start,
    date_end=split.train_end,
    dataset_manifest_id=manifest.content_hash,
    code_commit=current_git_commit(),
    metrics={"sharpe": 0.82},
))
```

### Step 4 — Tune on VALIDATION only

Once a candidate signal is developed on train, evaluate it on the **validation**
window.  You may iterate (choose lookback, threshold, position sizing) on
validation — but **every iteration adds to the trial count**.

Check the trial count regularly:

```python
from trader.research.experiment_log import multiple_testing_warning
n = log.trial_count(kind="momentum", strategy="cross_sectional_momentum")
print(multiple_testing_warning(n))
```

When the warning reaches "⚠️ 10+ trials", slow down.  Require a meaningful
economic rationale for each new trial, not just a grid search.

### Step 5 — ONE final check on HOLDOUT

After all development and tuning is complete, touch the holdout **exactly once**:

```python
holdout_bars = filter_bars_to_window(bars, split.holdout_start, split.holdout_end)
result = cross_sectional_momentum(holdout_bars, ...)
```

Report the result alongside:
- `trial_count` from the experiment log
- The `multiple_testing_warning` message
- The `PeriodSplit` used (so the holdout window is visible)
- The `dataset_manifest_id` (so the data is traceable)

If the holdout result is disappointing, **do not adjust and re-run**.  That would
convert the holdout into a third tuning set and invalidate the entire process.
Instead, accept the result and start a new, independently pre-registered experiment.

---

## What invalidates a holdout

- Looking at holdout performance before finalising all parameters.
- Changing the holdout boundaries after seeing results.
- Running the full universe on the holdout "just to check" mid-development.
- Choosing the primary metric after seeing the holdout result.

Any of these actions mean the reported holdout result is NOT a valid
out-of-sample estimate.  Label it honestly as "contaminated" in the log.

---

## Reporting checklist

Every published result must include:

- [ ] Pre-registered hypothesis (what was the signal, why did you believe it?)
- [ ] `PeriodSplit` — exact train / validation / holdout boundaries
- [ ] `trial_count` — how many experiments were run before this result
- [ ] `multiple_testing_warning(trial_count)` output
- [ ] `dataset_manifest_id` — which data snapshot was used
- [ ] `code_commit` — which code produced the result
- [ ] Honest statement of whether the holdout was touched once or multiple times

---

## References

- Harvey, Liu, Zhu (2016) — "… and the Cross-Section of Expected Returns" (JF)
- Bailey, Lopez de Prado (2014) — "The Deflated Sharpe Ratio"
- Prado (2018) — "Advances in Financial Machine Learning", Chapter 8
