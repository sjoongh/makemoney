# Data Limitations and Research Caveats

> **This document is mandatory reading before interpreting any backtest or
> momentum research output from this codebase.**

---

## 1. Survivorship Bias (Critical)

**What it is:** The universe used for research (`trader/data/universe.py`)
consists of *current* S&P 500 and KOSPI large-cap constituents — companies
that exist and trade today.  Companies that were delisted, went bankrupt,
were merged away, or were removed from the index at any point in history are
**absent**.

**Why it matters:** These absent names are disproportionately losers.
Momentum, trend-following, and quality-factor strategies look dramatically
better when tested only on survivors because the worst-performing names are
excluded by construction.  Literature estimates of survivorship-bias inflation
range from +1 % to +5 % CAGR depending on factor and universe.

**What is NOT supported:** Any claim of live trading edge, alpha, or
statistical significance derived from this universe.

**What IS required for a credible claim:** Point-in-time index membership
data (e.g. S&P 500 additions/removals history, KOSPI constituent snapshots
with effective dates).  This codebase does not yet have that data.

---

## 2. Point-in-Time Membership Absent

The `universe()` function in `trader/data/universe.py` fetches the current
S&P 500 CSV from a GitHub dataset and uses a hardcoded KOSPI large-cap list.
Neither source provides historical membership dates.  As a result:

- A company added to the S&P 500 in 2020 will appear in backtests starting
  from 2015 — introducing forward-looking look-ahead on index membership.
- A company removed in 2022 will be absent even from periods when it was
  a valid constituent.

Both effects bias results upward.

---

## 3. Single Source Per Market

| Market | Source | Limitation |
|--------|--------|-----------|
| NASDAQ / US equities | Yahoo Finance (via `yfinance`) | Rate-limited; throttles aggressive fetchers; 429 errors cause symbol skips |
| KOSPI / KR equities | Naver Finance (via `trader/data/naver_provider.py`) | Unadjusted prices (see §4) |

No cross-source validation is performed.  A single bad fetch silently
produces a gap or stale prices.

---

## 4. Naver Unadjusted vs Yahoo Adjusted Prices

Yahoo Finance returns **split- and dividend-adjusted** closing prices.
Naver Finance returns **unadjusted** (raw) closing prices.

This means:

- For KOSPI symbols, a stock split or large dividend will appear as a
  price drop in the Naver data, which the momentum signal will interpret as
  negative momentum even if the economic return was flat or positive.
- Cross-market comparisons (US vs KR momentum scores) are not
  apples-to-apples.

**Mitigation required:** Use an adjusted-price source for KOSPI, or apply
a split/dividend adjustment layer before computing signals.

---

## 5. NAVER 035420 Data Corruption — Quarantined

NAVER Corp (ticker `035420`) has known price data corruption in the Naver
Finance feed: anomalous price spikes or gaps appear that do not correspond
to actual trades.  This symbol is considered **quarantined** for research
purposes until a clean adjusted-price source is confirmed.

When `035420` is included in momentum research, its momentum scores should
be treated as unreliable and its rebalance log entries inspected manually.

---

## 6. Calendar / Holiday Heuristic Limits

The momentum backtest identifies trading days by building a union of all
dates present in the provided price data.  No exchange calendar is enforced.
Implications:

- If a symbol has a missing date (holiday, suspension, data gap), the union
  calendar will still include that date for other symbols but not for the
  gapped symbol — which is handled conservatively (missing price = flat
  contribution), but may distort period returns.
- Monthly rebalance detection uses a simple calendar-month boundary check
  (`month != prev_month`).  This does not account for market closures at
  month boundaries, which can shift the effective rebalance date by 1–2 days.

---

## 7. What Claims Are and Are Not Supportable

| Claim | Supportable? | Why |
|-------|-------------|-----|
| "The backtest engine executes orders in the correct order" | Yes | Engine-validation tests cover this deterministically |
| "Momentum factor has positive alpha in this universe" | **No** | Survivorship bias, no point-in-time membership |
| "Strategy X beats buy-and-hold in this universe" | **No** (exploratory only) | Same bias; in-sample only |
| "Transaction costs are modelled accurately" | Partially | KOSPI STT and NASDAQ SEC/TAF rates are hardcoded approximations |
| "Results are reproducible" | Yes | Manifest stamps record fetch timestamps and bar counts |
| "This strategy is ready to trade live" | **No** | No out-of-sample validation, no point-in-time universe |

---

## 8. How to Reduce These Limitations

1. **Survivorship bias:** Obtain historical constituent membership lists
   (e.g. from Bloomberg, Compustat, or open-source CRSP equivalents).
   Replace `universe()` with a point-in-time membership lookup keyed on
   the backtest date.

2. **Adjusted prices for KOSPI:** Integrate a data source that provides
   split- and dividend-adjusted KOSPI prices (e.g. FnGuide, QuantiWise,
   or KRX official adjusted series).

3. **Walk-forward validation:** Split the data into an in-sample
   optimisation window and a strictly held-out out-of-sample test window.
   Report results on the out-of-sample window only.

4. **Market-index benchmark:** Supply an externally-fetched SPY or KOSPI
   index return series to `format_report()` as the primary benchmark.
   The equal-weight universe benchmark built into `evaluate()` is
   survivorship-biased for the same reason the strategy universe is.

5. **035420 quarantine:** Either exclude `035420` from the universe until
   an adjusted source is confirmed, or add a data-integrity check that
   flags implausible price moves (e.g. > 30 % single-day moves on no news).

---

*Last updated: see git log.  All output from `format_report()` and
`format_momentum_report()` includes a canonical survivorship-bias warning
sourced from `trader/research/disclaimers.py`.*
