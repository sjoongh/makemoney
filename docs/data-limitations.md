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

## 3. Single Source — yfinance (both markets)

| Market | Source | Symbol form | Adjustment |
|--------|--------|-------------|-----------|
| NASDAQ / US equities | yfinance | `AAPL` | split/dividend adjusted |
| KOSPI / KR equities  | yfinance | `005930.KS` | split/dividend adjusted |

As of 2026-06-22 **both markets use yfinance** (`_default_research_us_downloader`
in `trader/data/research_provider.py`).  Rationale: the raw Yahoo chart JSON API
began returning HTTP 429 on every call, and Naver's sise XML intermittently
served corrupt OHLC and is unadjusted.  yfinance (curl_cffi browser
impersonation) is clean, adjusted, and consistent across markets.

Still a **single source** — no cross-source validation.  Mitigations now in
place at fetch time:
- **Retry with backoff** on empty / malformed / systemically-inconsistent
  downloads (transient yfinance glitches re-fetch clean).
- **Sub-epsilon FP clamping** of adjusted-price high/low rounding noise.
- **Isolated bad-bar drop** (logged): a bar still OHLC-inconsistent after
  clamping is dropped; if dropped bars exceed `max(5, 0.5%)` the whole symbol
  fails (so systemic corruption is rejected, not silently thinned).

Naver (`_fetch_naver`) is retained as an **audit/fallback** source only and is
no longer wired into `daily_history`.

---

## 4. Source Migration — Reproducibility Caveat

KOSPI data was previously sourced from Naver as **raw (unadjusted)** prices.
It is now yfinance **adjusted** prices.  Adjusted is the correct default for
return/momentum/drawdown research (it preserves return continuity across splits
and dividends), and it makes US and KR semantically comparable.

**However:** KOSPI backtests run before this migration used raw Naver data and
are **NOT directly comparable** to runs on the new adjusted `.KS` data.  Dataset
manifests record `provider` and `adjustment` per file (`provider="yfinance"`,
`adjustment="adjusted"`) so old vs new runs can be told apart by hash/manifest.
Treat any pre-migration KOSPI result as a different dataset.

---

## 5. Calendar / Holiday Heuristic Limits

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

## 6. What Claims Are and Are Not Supportable

| Claim | Supportable? | Why |
|-------|-------------|-----|
| "The backtest engine executes orders in the correct order" | Yes | Engine-validation tests cover this deterministically |
| "Momentum factor has positive alpha in this universe" | **No** | Survivorship bias, no point-in-time membership |
| "Strategy X beats buy-and-hold in this universe" | **No** (exploratory only) | Same bias; in-sample only |
| "Transaction costs are modelled accurately" | Partially | KOSPI STT and NASDAQ SEC/TAF rates are hardcoded approximations |
| "Results are reproducible" | Yes | Manifest stamps record fetch timestamps and bar counts |
| "This strategy is ready to trade live" | **No** | No out-of-sample validation, no point-in-time universe |

---

## 7. How to Reduce These Limitations

1. **Survivorship bias:** Obtain historical constituent membership lists
   (e.g. from Bloomberg, Compustat, or open-source CRSP equivalents).
   Replace `universe()` with a point-in-time membership lookup keyed on
   the backtest date.

2. **Adjusted prices for KOSPI:** ✅ Done (2026-06-22) — KOSPI now uses
   yfinance `.KS` (split/dividend adjusted), replacing raw Naver.  See §3–4.

3. **Walk-forward validation:** Split the data into an in-sample
   optimisation window and a strictly held-out out-of-sample test window.
   Report results on the out-of-sample window only.

4. **Market-index benchmark:** Supply an externally-fetched SPY or KOSPI
   index return series to `format_report()` as the primary benchmark.
   The equal-weight universe benchmark built into `evaluate()` is
   survivorship-biased for the same reason the strategy universe is.

5. **035420 (NAVER Corp):** The old Naver-feed corruption was source-specific;
   `035420` now fetches clean via yfinance `.KS` and passes the quality gate.
   The fetch-time integrity checks (§3) flag implausible bars going forward.

---

*Last updated: see git log.  All output from `format_report()` and
`format_momentum_report()` includes a canonical survivorship-bias warning
sourced from `trader/research/disclaimers.py`.*
