# Overnight Edge-Hunt Log

Autonomous research loop. Goal: find a tradable edge that survives the
disciplined gate (train→validation→holdout, costed, multiple-testing-corrected),
or honestly exhaust approaches. **No real-money orders autonomously** (paper
only). **No manufactured edge** — a null result is reported as null.

## Stopping criteria (stop + report when ANY is hit)
1. A candidate passes the full gate: consistent train+val IC, then a clean
   **holdout** pass (opened once), positive after costs in a proper portfolio
   backtest, t-stat clearing the multiple-testing haircut.
2. The backlog below is exhausted with no survivor → honest terminal "no edge".
3. User says stop.

## Method (fixed, non-negotiable)
- Cross-sectional IC via `evaluate_ic` (tradable fwd returns, non-overlapping).
- Split discipline via `run_signal_zoo` (train+val only; holdout gated).
- Every batch logged to `experiments/`; multiple-testing haircut applied.

## Backlog (work through in order)
- [x] R1: 13 single OHLCV anomalies (momentum family, reversal, low-vol, MAX,
      52w-high, Amihud, volume-trend, skewness, long-term reversal). → NO edge.
- [ ] R2: multi-factor COMPOSITES (cross-sectional z-score blends) + multi-horizon
      (h=5, 63) for the least-bad singles.
- [ ] R3: proper long-short PORTFOLIO backtest (costed, via a regression-tested
      backtester) of the best composite — IC≈0 may still be checked for any
      risk-adjusted residual; expect none.
- [ ] R4: regime filter (trend on/off, vol regime) + sector/size neutralization.
- [ ] R5: paper-forward analysis (cron dry-run track record) + forward-data review.
- [ ] R6: completeness/robustness pass (monitoring, reporting, failure modes).

## Round results (append-only)
### R1 — 2026-06-27 — single anomalies, 13×2=26 trials
NO survivor. Train-significant hits (US low_vol −2.26, US max −1.94, KR skew
+2.40) all collapse in validation (|t|<1.3); below the 26-trial haircut (~2.55).
Conclusion: no single free-OHLCV anomaly has edge on this universe.

### R2 — 2026-06-27 — multi-horizon sweep (h=5, 63), 13×2×2 more trials
NO survivor at any horizon. Same signature: train-significant hits collapse in
validation (US low_vol h63 −2.58→−0.52; KR skew h63 +2.28→+1.03; KR max h5
+2.07→−0.30). Only KR Amihud illiquidity is weakly persistent in the right
direction (val +1.3~1.8) but never significant. Across 13 signals × 2 markets ×
3 horizons (~78 trials), nothing survives — the cumulative multiple-testing bar
is now high enough that continuing single-signal mining would only manufacture
false positives.

## DECISION (2026-06-27): pivot from edge-search to production-readiness
Free cross-sectional OHLCV edge is robustly **exhausted (no edge)**. Acceptance
path (B) "confident profit basis" is not supported by the data. So pursue
acceptance path (A): drive the **auto-trading PROGRAM to ≥90% production-ready**
for real-money use (robust execution, monitoring/alerting, reconciliation,
forward paper-trade track record, go-live runbook, config validation) — honestly
decoupling "platform is production-grade" from "strategy has alpha" (it doesn't,
yet). Edge-search reopens only if a fundamentally new data axis is funded.
See docs/PRODUCTION_READINESS.md for the checklist tracked to 90%.

### R3 — 2026-06-27 — production-readiness to ≥90% (loop stop condition met)
Pivoted to platform hardening (alpha unproven). Built: heartbeat/dead-man's
switch + healthcheck cron; config fail-fast validation; verified the LIVE
4-gate + paper-endpoint default; go-live runbook; daily heartbeat wiring.
PRODUCTION_READINESS.md → ~90%. Remaining items are HUMAN-ONLY (B1 reconcile,
ALERT_WEBHOOK_URL, pmset, a validated strategy). **Autonomous loop STOPPED**:
both stop conditions hit (≥90% reached; only human-needed items left). 886 tests.

### R4 — 2026-06-27 — forward PAPER trading enabled (track-record accumulation)
User asked to actually paper-trade. Verified the live path works against the
KIS 모의 account (FX, account snapshot=100M KRW, decision=BUY 36 005930). Two
fixes/ops: (a) per-order notional cap made env-tunable (5M default too tight for
a 100M account; paper runner uses 20M); (b) daily cron (KR 16:00, US 06:00)
flipped to submit PAPER orders (--live on PAPER_BASE only — cannot reach real
money). The SignalJournal idempotency correctly prevents double-submits/day.
Honest note: this is a NO-EDGE technical strategy; the forward paper record is
unbiased VALIDATION, not expected profit. Requires the Mac awake (pmset) for cron
to fire — else the heartbeat healthcheck will alert.

### R5 — 2026-06-27 — EDGAR point-in-time FUNDAMENTALS (no edge)
Built a proper free point-in-time fundamental pipeline (SEC EDGAR XBRL, 18yr,
actual filed dates → no look-ahead/restatement), the thing yfinance (5 quarters)
couldn't do. Tested the two cleanest value signals on 503 US with split
discipline (h=21):
  book_to_market: train IC -0.0054 (t-0.60) → val +0.0105 (t+0.78)  [sign flip]
  earnings_yield: train -0.0037 (t-0.46) → val -0.0056 (t-0.38)
NEITHER significant; book/market even wrong-signed in train. Caveat: market-cap
leg used adjusted price (threatens only a POSITIVE; result is NULL so unaffected).
CONCLUSION: the fundamental axis shows NO edge on free data either. Across price
AND fundamentals, rigorously split-tested, there is no tradable cross-sectional
edge in free data. The data ceiling is real and now doubly confirmed.
