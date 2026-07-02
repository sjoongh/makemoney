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

### R6 — 2026-06-29 — FRED macro REGIME conditioning (no alpha; beta artifact)
Added keyless FRED (trader/data/fred.py) + evaluate_ic allowed_dates regime
filter. Yield-curve (T10Y2Y) normal vs inverted, momentum & low-vol (h=21):
  momentum_12_1: normal +0.011 (t0.54) / inverted +0.052 (t1.30) — n.s.
  low_vol_60:    normal -0.067 (t-2.74) / inverted -0.060 (t-1.31)
The lone |t|>2 (low-vol normal-regime) is WRONG-SIGNED for the anomaly: it means
high-vol/high-BETA names outperform in calm markets — beta-timing, not alpha;
full-sample (no holdout); inverts in the stress regime → not robust. Conclusion:
no alpha edge; the only thing that "works" is market BETA in calm regimes. This
justifies pivoting to the beta game (Task 3): own the market with risk management.

### R7 — 2026-06-29 — the BETA GAME (constructive, honest, works)
No alpha → own the market with risk management. Vol-targeted equal-weight US
(EWMA target vol) vs naive buy&hold, 2016-2026 (2518 days):
  target_vol=15%: vol-tgt CAGR 15.2% / vol 13.1% / Sharpe 1.15 / MaxDD -19.2%
                  buy&hold CAGR 18.2% / vol 18.6% / Sharpe 0.99 / MaxDD -38.3%
Gives up raw CAGR (no alpha) but BETTER Sharpe and ~HALF the drawdown. This is
the honest deliverable: a better risk-adjusted way to own market BETA, not a
skill edge. Caveats: survivorship-biased universe (real return lower); exposure-
change costs not modeled; beta-dependent (needs market to rise). trader/research/
beta_game.py + run_beta_game CLI; 3 tests.

## FINAL STANDING (2026-06-29)
Free-data ALPHA: exhaustively searched (price R1-2, fundamentals/EDGAR R5, macro
regime R6) — NONE. The only thing that "works" is risk-managed BETA (R7). Honest
end state: a production-grade platform + a vol-targeted beta strategy that owns
the market safely. Real alpha needs paid alt-data, or accept beta.

### R8 — 2026-07-01 — PEAD / filing-date earnings drift (SUE), large-cap: no edge
Built estimate-free, drift-adjusted SUE from EDGAR point-in-time NI+filing dates
(edgar.sue_as_of, make_sue). US large-cap, split-disciplined:
  h21 train -0.0088(t-0.89) → val +0.0229(t+1.89); h63 train -0.019 → val +0.032
Sign FLIPS train→val, none significant (|t|<2). Large-cap PEAD is dead (matches
"Rest in Peace PEAD", Martineau). The val positive IC (right direction) hints it
may survive in SMALL/neglected caps — Axis 2 pending micro-cap data feasibility.
Honest odds (Codex) for a real after-cost small-cap edge: 10-25% with strict
liquidity/delisting controls, <10% on survivorship-biased free names.

### R9 — 2026-07-01 — KOSDAQ small-caps: signal EXISTS but not tradable after costs
Axis 2. Survivorship-lighter KOSDAQ small-caps via FDR (146 liquidity-filtered
names, incl. some delisted). Technical battery, split-disciplined (h=21): unlike
large-caps, several signals kept CONSISTENT sign train→val — 21d reversal
(train t+2.89 / val +1.16), MAX/lottery (+2.55/+1.32), Amihud illiquidity
(+1.13/+1.43). Reversal SURVIVED the bid-ask-bounce test (skip last 5 days → val
t rose to +2.03) → not a bounce artifact; the first genuinely train+val-significant
signal of the whole hunt.
BUT the DECISIVE cost test killed it: long-only top-20% reversal, monthly rebal,
1.5% round-trip cost → TRAIN +11.4% vs bench +25.7% (−14.3%), VAL −16.8% vs
−2.0% (−14.8%). Gross edge ~3%/yr is entirely eaten by ~18%/yr turnover cost.
CONCLUSION: small-cap anomalies (reversal/MAX/illiquidity) genuinely EXIST in the
data but are NOT tradable after realistic frictions — which is precisely why they
persist (uncapturable = unarbitraged). No free-data tradable alpha, now confirmed
even in the less-arbitraged corner. (Caveats: current-listing universe still
somewhat survivorship-biased; long-only; no holdout opened — but a strategy that
loses to benchmark after costs in BOTH train and val doesn't warrant a holdout.)

### R10 — 2026-07-02 — ULTRACODE full-system audit → paper-trading correctness fixes
User sensed "약간 이상해" — a 32-agent audit (5 dimensions, adversarially verified)
confirmed he was right. CRITICAL: (1) account_snapshot used dnca_tot_amt (D+0
gross deposit, never decreases on buys) as cash, and KIS-paper overseas buys are
funded from a phantom pool that never debits domestic KRW → (2) each sleeve saw
equity = full stale cash + own position → compounding daily OVER-BUY (89M
deployed on 99.6M true equity = 90% vs ~65% intended; replay predicted +11 more
SPY tonight). HIGH: no same-day idempotency (double-submit actually happened
07-01), pretrade caps bypassed, EW index tail computed from 3/200 names (+4.88%
garbage) fed vol targeting, no data-recency gate, FX silently fell back to 1380,
healthcheck didn't monitor the only order-submitting jobs, 13:00 accumulator
stored PARTIAL intraday KOSPI bars.
FIXES: settled-cash (prvs_rcdl_excc_amt) + virtual overseas debit + nass_krw in
account_snapshot; rebalance_order takes explicit SHARED equity; executor rebuilt
(idempotency/day, FX gate, coverage-floor+partial-bar-excluding robust index,
recency abort, notional/fat-finger/weight caps); healthcheck now watches
beta_kis_kr/us (+.env webhook); accumulate cron 13:00→16:10 KST (post-close);
buggy track archived (beta_kis_track.buggy-sizing.jsonl.bak). Verified: KR now
HOLD at true equity 99.64M; US SELL 22 SPY self-heals tonight. 926 tests.
Known follow-ups: sp500 cache never auto-refreshes (30d refresh), accumulator
provider_for still maps KOSPI→naver (cooldown isolation ineffective).
