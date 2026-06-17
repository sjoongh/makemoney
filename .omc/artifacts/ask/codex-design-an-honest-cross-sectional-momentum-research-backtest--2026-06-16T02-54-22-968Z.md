# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-16T02:54:22.969Z

## Original task

Design an HONEST cross-sectional momentum research backtest (separate from my live event engine — this is hypothesis validation, not live code yet). I have keyless daily OHLCV for a modest universe (constraint: ~10-25 stocks max, mix of US large-cap + KR KOSPI, ~5-25yr history depending on symbol; data via Yahoo/Naver, rate-limited so universe is small).

Tersely specify the CANONICAL spec + an honest test protocol that won't fool me at this small scale:
1. Signal: trailing momentum — lookback & skip (classic 12-1 = 12mo return skipping most recent 1mo)? On daily bars, how many trading days = 12mo/1mo? 
2. Rebalance frequency (monthly?), ranking, hold top-K (K relative to universe size), equal-weight, long-only (we're long/cash).
3. Benchmark: equal-weight buy&hold of the SAME universe (not a single stock) + cash. Why this is the fair benchmark.
4. Costs: apply our MarketCostModel per rebalance turnover.
5. HONEST test protocol at small N: what can/can't be concluded with ~15 stocks? In-sample vs walk-forward? Report what metrics (CAGR, vol, Sharpe, MaxDD, turnover, hit-rate, vs benchmark). Multiple-testing/overfitting traps to avoid (don't sweep K/lookback and report the best). 
6. The KNOWN failure modes of cross-sectional momentum (crashes/reversals, small-universe noise, survivorship if I hand-pick tickers — how to avoid survivorship bias in universe selection).
7. Honest expectation: at this universe size, is a positive result meaningful? What would I need for it to be credible?
Give a concrete spec (numbers) + the metrics table to produce. Senior quant, terse, no hype.

## Final prompt

Design an HONEST cross-sectional momentum research backtest (separate from my live event engine — this is hypothesis validation, not live code yet). I have keyless daily OHLCV for a modest universe (constraint: ~10-25 stocks max, mix of US large-cap + KR KOSPI, ~5-25yr history depending on symbol; data via Yahoo/Naver, rate-limited so universe is small).

Tersely specify the CANONICAL spec + an honest test protocol that won't fool me at this small scale:
1. Signal: trailing momentum — lookback & skip (classic 12-1 = 12mo return skipping most recent 1mo)? On daily bars, how many trading days = 12mo/1mo? 
2. Rebalance frequency (monthly?), ranking, hold top-K (K relative to universe size), equal-weight, long-only (we're long/cash).
3. Benchmark: equal-weight buy&hold of the SAME universe (not a single stock) + cash. Why this is the fair benchmark.
4. Costs: apply our MarketCostModel per rebalance turnover.
5. HONEST test protocol at small N: what can/can't be concluded with ~15 stocks? In-sample vs walk-forward? Report what metrics (CAGR, vol, Sharpe, MaxDD, turnover, hit-rate, vs benchmark). Multiple-testing/overfitting traps to avoid (don't sweep K/lookback and report the best). 
6. The KNOWN failure modes of cross-sectional momentum (crashes/reversals, small-universe noise, survivorship if I hand-pick tickers — how to avoid survivorship bias in universe selection).
7. Honest expectation: at this universe size, is a positive result meaningful? What would I need for it to be credible?
Give a concrete spec (numbers) + the metrics table to produce. Senior quant, terse, no hype.

## Raw output

```text
**Canonical Spec**

1. **Universe**
   - Fixed ex-ante list of ~15 liquid names, mixed US large-cap + KR KOSPI.
   - Include only symbols with usable OHLCV at each rebalance date.
   - Do not require all names to have full history; rank only among names with enough lookback data.
   - Cash return: either 0% or daily risk-free proxy if available. Pick one before testing.

2. **Signal**
   - Cross-sectional trailing momentum: **12-1 momentum**.
   - Daily implementation:
     - 12 months = `252` trading days.
     - 1 month skip = `21` trading days.
     - Signal at rebalance date `t`:

   ```text
   mom_12_1 = close[t - 21] / close[t - 252] - 1
   ```

   - Requires at least `252` trading days of adjusted close history.
   - Use adjusted close for signal and total-return realism where possible.
   - Do not use today’s close to form a trade executed at today’s close unless you explicitly model that timing. Cleaner: compute signal after month-end close, trade next session open/close.

3. **Rebalance**
   - Frequency: **monthly**, first trading day after month-end signal date.
   - Rank all eligible stocks by `mom_12_1`, descending.
   - Hold top `K`.
   - Concrete `K`:
     - If universe size `N <= 10`: hold top `3`.
     - If `10 < N <= 20`: hold top `5`.
     - If `20 < N <= 25`: hold top `6`.
   - Or simpler canonical rule: **hold top 30% of eligible universe, rounded to nearest integer, minimum 3, maximum 6**.
   - Long-only, equal-weight.
   - Non-selected capital goes to cash only if fewer than `K` eligible names exist or a position cannot be held.
   - No short leg.

4. **Execution**
   - At rebalance, target equal weights among selected names.
   - Between rebalances, weights drift naturally.
   - Turnover:

   ```text
   turnover_t = 0.5 * sum(abs(target_weight_i - pre_trade_weight_i))
   ```

   - Apply `MarketCostModel` on traded notional per rebalance.
   - Costs must include both exits and entries.
   - If the model is side-specific or market-specific, apply US/KR assumptions separately.

5. **Benchmark**
   - Benchmark is **equal-weight buy-and-hold of the same universe**, plus the same cash treatment.
   - Initialize equal weights across all names that are eligible at the strategy start.
   - Rebalance benchmark either:
     - Preferred: monthly equal-weight rebalance to same currently eligible universe, with same costs; or
     - Secondary: true buy-and-hold, no rebalance, no costs.
   - For momentum validation, the fair primary benchmark is **same universe, equal-weight monthly rebalanced, same data availability, same costs**.

Why: the question is whether cross-sectional ranking adds value relative to owning the opportunity set. A single index or single stock confounds country mix, sector mix, currency, survivorship, and universe choice.

---

**Concrete Test Protocol**

Use one canonical test first:

```text
Signal:        252-day return skipping most recent 21 trading days
Rebalance:     Monthly
Portfolio:     Long-only top 30%, min 3 max 6 names
Weights:       Equal-weight
Benchmark:     Equal-weight same-universe monthly rebalance
Costs:         MarketCostModel on turnover
Cash:          Predefined 0% or risk-free proxy
Trade timing:  Signal from month-end close, trade next trading day
```

Do not sweep parameters first.

If testing variants, pre-register a tiny grid and report all results:

```text
Lookback/skip:
- 126-21
- 252-21
- 252-0

K:
- top 20%
- top 30%
- top 40%
```

But the canonical result remains `252-21`, top 30%. Do not choose the best and call it the strategy.

---

**Metrics Table**

Produce this table for strategy, benchmark, and strategy minus benchmark:

| Metric | Momentum | Same-Universe EW Benchmark | Difference |
|---|---:|---:|---:|
| Start date | | | |
| End date | | | |
| Number of stocks avg/min/max | | | |
| CAGR | | | |
| Annualized volatility | | | |
| Sharpe | | | |
| Max drawdown | | | |
| Calmar | | | |
| Monthly hit rate | | | |
| Annual hit rate | | | |
| Best month | | | |
| Worst month | | | |
| Average monthly turnover | | | |
| Total turnover | | | |
| Gross CAGR before costs | | | |
| Net CAGR after costs | | | |
| Cost drag annualized | | | |
| Excess CAGR vs benchmark | | | |
| Tracking error vs benchmark | | | |
| Information ratio | | | |
| Beta to benchmark | | | |
| Worst relative drawdown | | | |

Also report:

```text
Number of rebalance periods
Average names held
Percent time in cash
Top contributors
Worst contributors
Country exposure over time
Sector exposure if available
```

---

**Small-N Honesty Rules**

With ~15 stocks, this is not a statistically strong test of cross-sectional momentum. It is a sanity check.

You can conclude:

```text
This rule would/would not have improved this specific hand-sized universe historically.
Turnover and costs are/are not fatal.
The return profile is/is not obviously dominated by one or two names.
The strategy is/is not robust to basic implementation choices.
```

You cannot honestly conclude:

```text
Cross-sectional momentum works generally.
The edge is statistically proven.
The selected parameter set is optimal.
The live strategy has positive expected alpha.
```

At small N, one mega-winner, one country regime, one FX cycle, or one sector tilt can dominate the whole result.

---

**In-Sample / Walk-Forward**

For 10-25 names, avoid pretending walk-forward optimization proves much.

Better protocol:

1. Pick the canonical rule before looking at results.
2. Run full-history backtest.
3. Split into chronological thirds:
   - early
   - middle
   - recent
4. Report metrics for each subperiod.
5. Require the strategy to not rely entirely on one subperiod.
6. If testing parameters, choose them using only the first half, then report the second half untouched.

Do not optimize lookback, skip, rebalance day, K, volatility scaling, stop losses, country filters, and cost assumptions all on the same tiny sample.

---

**Multiple-Testing Traps**

Avoid:

```text
Trying many lookbacks and reporting only the best.
Changing K after seeing drawdowns.
Dropping bad tickers after seeing results.
Starting the test after a bad period.
Mixing adjusted and unadjusted prices inconsistently.
Ignoring delisted stocks.
Ignoring FX if returns are compared in one base currency.
Using future universe membership.
Using today’s close signal and same close execution.
Reporting pre-cost returns as the headline.
```

Keep a research log. Every change after seeing results is in-sample.

---

**Known Failure Modes**

1. **Momentum crashes**
   - Sharp reversals after market stress.
   - Prior losers rebound violently.
   - Long-only top-rank portfolio can lag badly in recovery phases.

2. **Small-universe noise**
   - Ranking 15 names is fragile.
   - A rank difference between #5 and #6 may be meaningless.
   - Holdings can become concentrated in one sector/country regime.

3. **Survivorship bias**
   - Hand-picking current winners overstates performance.
   - Avoid by defining universe using historical membership or an ex-ante rule.

Better universe construction:

```text
US: choose top liquid names from a historical date, not today's favorites.
KR: choose KOSPI names from a historical date or rule-based liquidity screen.
Include names that later underperformed, merged, or delisted if data can be sourced.
Freeze the universe definition before testing.
Document why each ticker is included.
```

If you cannot get delisted data, label the result explicitly:

```text
Survivorship-biased current-constituent test.
Not evidence of deployable alpha.
```

---

**Honest Expectation**

A positive result with ~15 stocks is only mildly meaningful.

It becomes more credible if:

```text
It beats the same-universe benchmark after costs.
It works across early/middle/recent subperiods.
It is not driven by one stock or one country.
It survives reasonable cost increases.
It has tolerable drawdowns and turnover.
The canonical 252-21 rule works without parameter mining.
A few nearby variants produce similar, not wildly different, results.
The universe was selected ex-ante or rule-based, not hand-picked after the fact.
```

Minimum credibility bar:

```text
Net excess CAGR > 0 versus same-universe EW benchmark
Information ratio meaningfully positive
Max relative drawdown acceptable
Cost drag not consuming the edge
No single name explains most of the outperformance
Recent out-of-sample period does not collapse
```

Bottom line: for this universe size, treat the backtest as **hypothesis triage**, not proof. A clean positive result says “worth expanding the universe and data quality.” It does not say “ready for capital.”


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019ece59-40a6-7f73-9ac9-2b183bd2bdab
--------
user
Design an HONEST cross-sectional momentum research backtest (separate from my live event engine — this is hypothesis validation, not live code yet). I have keyless daily OHLCV for a modest universe (constraint: ~10-25 stocks max, mix of US large-cap + KR KOSPI, ~5-25yr history depending on symbol; data via Yahoo/Naver, rate-limited so universe is small).

Tersely specify the CANONICAL spec + an honest test protocol that won't fool me at this small scale:
1. Signal: trailing momentum — lookback & skip (classic 12-1 = 12mo return skipping most recent 1mo)? On daily bars, how many trading days = 12mo/1mo? 
2. Rebalance frequency (monthly?), ranking, hold top-K (K relative to universe size), equal-weight, long-only (we're long/cash).
3. Benchmark: equal-weight buy&hold of the SAME universe (not a single stock) + cash. Why this is the fair benchmark.
4. Costs: apply our MarketCostModel per rebalance turnover.
5. HONEST test protocol at small N: what can/can't be concluded with ~15 stocks? In-sample vs walk-forward? Report what metrics (CAGR, vol, Sharpe, MaxDD, turnover, hit-rate, vs benchmark). Multiple-testing/overfitting traps to avoid (don't sweep K/lookback and report the best). 
6. The KNOWN failure modes of cross-sectional momentum (crashes/reversals, small-universe noise, survivorship if I hand-pick tickers — how to avoid survivorship bias in universe selection).
7. Honest expectation: at this universe size, is a positive result meaningful? What would I need for it to be credible?
Give a concrete spec (numbers) + the metrics table to produce. Senior quant, terse, no hype.
codex
**Canonical Spec**

1. **Universe**
   - Fixed ex-ante list of ~15 liquid names, mixed US large-cap + KR KOSPI.
   - Include only symbols with usable OHLCV at each rebalance date.
   - Do not require all names to have full history; rank only among names with enough lookback data.
   - Cash return: either 0% or daily risk-free proxy if available. Pick one before testing.

2. **Signal**
   - Cross-sectional trailing momentum: **12-1 momentum**.
   - Daily implementation:
     - 12 months = `252` trading days.
     - 1 month skip = `21` trading days.
     - Signal at rebalance date `t`:

   ```text
   mom_12_1 = close[t - 21] / close[t - 252] - 1
   ```

   - Requires at least `252` trading days of adjusted close history.
   - Use adjusted close for signal and total-return realism where possible.
   - Do not use today’s close to form a trade executed at today’s close unless you explicitly model that timing. Cleaner: compute signal after month-end close, trade next session open/close.

3. **Rebalance**
   - Frequency: **monthly**, first trading day after month-end signal date.
   - Rank all eligible stocks by `mom_12_1`, descending.
   - Hold top `K`.
   - Concrete `K`:
     - If universe size `N <= 10`: hold top `3`.
     - If `10 < N <= 20`: hold top `5`.
     - If `20 < N <= 25`: hold top `6`.
   - Or simpler canonical rule: **hold top 30% of eligible universe, rounded to nearest integer, minimum 3, maximum 6**.
   - Long-only, equal-weight.
   - Non-selected capital goes to cash only if fewer than `K` eligible names exist or a position cannot be held.
   - No short leg.

4. **Execution**
   - At rebalance, target equal weights among selected names.
   - Between rebalances, weights drift naturally.
   - Turnover:

   ```text
   turnover_t = 0.5 * sum(abs(target_weight_i - pre_trade_weight_i))
   ```

   - Apply `MarketCostModel` on traded notional per rebalance.
   - Costs must include both exits and entries.
   - If the model is side-specific or market-specific, apply US/KR assumptions separately.

5. **Benchmark**
   - Benchmark is **equal-weight buy-and-hold of the same universe**, plus the same cash treatment.
   - Initialize equal weights across all names that are eligible at the strategy start.
   - Rebalance benchmark either:
     - Preferred: monthly equal-weight rebalance to same currently eligible universe, with same costs; or
     - Secondary: true buy-and-hold, no rebalance, no costs.
   - For momentum validation, the fair primary benchmark is **same universe, equal-weight monthly rebalanced, same data availability, same costs**.

Why: the question is whether cross-sectional ranking adds value relative to owning the opportunity set. A single index or single stock confounds country mix, sector mix, currency, survivorship, and universe choice.

---

**Concrete Test Protocol**

Use one canonical test first:

```text
Signal:        252-day return skipping most recent 21 trading days
Rebalance:     Monthly
Portfolio:     Long-only top 30%, min 3 max 6 names
Weights:       Equal-weight
Benchmark:     Equal-weight same-universe monthly rebalance
Costs:         MarketCostModel on turnover
Cash:          Predefined 0% or risk-free proxy
Trade timing:  Signal from month-end close, trade next trading day
```

Do not sweep parameters first.

If testing variants, pre-register a tiny grid and report all results:

```text
Lookback/skip:
- 126-21
- 252-21
- 252-0

K:
- top 20%
- top 30%
- top 40%
```

But the canonical result remains `252-21`, top 30%. Do not choose the best and call it the strategy.

---

**Metrics Table**

Produce this table for strategy, benchmark, and strategy minus benchmark:

| Metric | Momentum | Same-Universe EW Benchmark | Difference |
|---|---:|---:|---:|
| Start date | | | |
| End date | | | |
| Number of stocks avg/min/max | | | |
| CAGR | | | |
| Annualized volatility | | | |
| Sharpe | | | |
| Max drawdown | | | |
| Calmar | | | |
| Monthly hit rate | | | |
| Annual hit rate | | | |
| Best month | | | |
| Worst month | | | |
| Average monthly turnover | | | |
| Total turnover | | | |
| Gross CAGR before costs | | | |
| Net CAGR after costs | | | |
| Cost drag annualized | | | |
| Excess CAGR vs benchmark | | | |
| Tracking error vs benchmark | | | |
| Information ratio | | | |
| Beta to benchmark | | | |
| Worst relative drawdown | | | |

Also report:

```text
Number of rebalance periods
Average names held
Percent time in cash
Top contributors
Worst contributors
Country exposure over time
Sector exposure if available
```

---

**Small-N Honesty Rules**

With ~15 stocks, this is not a statistically strong test of cross-sectional momentum. It is a sanity check.

You can conclude:

```text
This rule would/would not have improved this specific hand-sized universe historically.
Turnover and costs are/are not fatal.
The return profile is/is not obviously dominated by one or two names.
The strategy is/is not robust to basic implementation choices.
```

You cannot honestly conclude:

```text
Cross-sectional momentum works generally.
The edge is statistically proven.
The selected parameter set is optimal.
The live strategy has positive expected alpha.
```

At small N, one mega-winner, one country regime, one FX cycle, or one sector tilt can dominate the whole result.

---

**In-Sample / Walk-Forward**

For 10-25 names, avoid pretending walk-forward optimization proves much.

Better protocol:

1. Pick the canonical rule before looking at results.
2. Run full-history backtest.
3. Split into chronological thirds:
   - early
   - middle
   - recent
4. Report metrics for each subperiod.
5. Require the strategy to not rely entirely on one subperiod.
6. If testing parameters, choose them using only the first half, then report the second half untouched.

Do not optimize lookback, skip, rebalance day, K, volatility scaling, stop losses, country filters, and cost assumptions all on the same tiny sample.

---

**Multiple-Testing Traps**

Avoid:

```text
Trying many lookbacks and reporting only the best.
Changing K after seeing drawdowns.
Dropping bad tickers after seeing results.
Starting the test after a bad period.
Mixing adjusted and unadjusted prices inconsistently.
Ignoring delisted stocks.
Ignoring FX if returns are compared in one base currency.
Using future universe membership.
Using today’s close signal and same close execution.
Reporting pre-cost returns as the headline.
```

Keep a research log. Every change after seeing results is in-sample.

---

**Known Failure Modes**

1. **Momentum crashes**
   - Sharp reversals after market stress.
   - Prior losers rebound violently.
   - Long-only top-rank portfolio can lag badly in recovery phases.

2. **Small-universe noise**
   - Ranking 15 names is fragile.
   - A rank difference between #5 and #6 may be meaningless.
   - Holdings can become concentrated in one sector/country regime.

3. **Survivorship bias**
   - Hand-picking current winners overstates performance.
   - Avoid by defining universe using historical membership or an ex-ante rule.

Better universe construction:

```text
US: choose top liquid names from a historical date, not today's favorites.
KR: choose KOSPI names from a historical date or rule-based liquidity screen.
Include names that later underperformed, merged, or delisted if data can be sourced.
Freeze the universe definition before testing.
Document why each ticker is included.
```

If you cannot get delisted data, label the result explicitly:

```text
Survivorship-biased current-constituent test.
Not evidence of deployable alpha.
```

---

**Honest Expectation**

A positive result with ~15 stocks is only mildly meaningful.

It becomes more credible if:

```text
It beats the same-universe benchmark after costs.
It works across early/middle/recent subperiods.
It is not driven by one stock or one country.
It survives reasonable cost increases.
It has tolerable drawdowns and turnover.
The canonical 252-21 rule works without parameter mining.
A few nearby variants produce similar, not wildly different, results.
The universe was selected ex-ante or rule-based, not hand-picked after the fact.
```

Minimum credibility bar:

```text
Net excess CAGR > 0 versus same-universe EW benchmark
Information ratio meaningfully positive
Max relative drawdown acceptable
Cost drag not consuming the edge
No single name explains most of the outperformance
Recent out-of-sample period does not collapse
```

Bottom line: for this universe size, treat the backtest as **hypothesis triage**, not proof. A clean positive result says “worth expanding the universe and data quality.” It does not say “ready for capital.”
tokens used
3,951

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
