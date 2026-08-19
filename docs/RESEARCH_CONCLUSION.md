# Research Conclusion — makemoney

> **Status as of 2026-06-24:** the system is *execution-safe* and *research-safe*,
> and the honest research verdict is **no tradable edge has been found** in
> classic price-based signals on this universe. This document records how we got
> there so the conclusion is auditable and not re-litigated by vibes.

---

## 1. What is built and trustworthy

- **Engine:** event-driven; backtest == live decision path proven by mutation
  testing; next-bar-open fills (no look-ahead).
- **Execution:** KIS paper trading verified (US NASDAQ + KR KOSPI, KRW-settled
  with FX), resilient submitter, pre-trade gate, kill switch, ATR risk sizing,
  daily-loss kill.
- **Research foundation (F1–F7):** data-quality validator, independent PnL
  fixtures, look-ahead audit, dataset manifests + content hashing, survivorship
  disclaimers, slippage/cost realism, multiple-testing discipline.
- **Data:** 703 symbols (503 S&P 500 + 200 KOSPI) × ~10y daily OHLCV via
  yfinance, split/dividend adjusted, all pass the quality gate. Committed.
- **Truth machine:** cross-sectional IC harness (`signal_eval.py`) with tradable
  forward returns, non-overlapping windows, train/val/holdout date discipline,
  and a hash-gated "open the holdout once" mechanism (`holdout_gate.py`).
- **Forward recorder:** daily point-in-time RAW bars + universe membership log —
  builds a *survivorship-free* forward dataset going forward (cron, daily).

## 2. What the evidence says — no edge

Measured cross-sectional Information Coefficient (does a signal's ranking predict
forward returns?) for a battery of classic signals, h = 21 trading days.

**Full-sample (exploratory), bigger universe weakened the signals:**

| signal | N≈120/30 | N=503/200 |
|---|---|---|
| US 12-1 momentum | t=1.63 | t=1.30 |
| US 5d reversal | t=−1.74 | t=−0.43 |
| KR 12-1 momentum | t=1.68 | t=1.19 |

Adding statistical power and watching the near-misses fade resolved the
"no edge vs no power" ambiguity toward **no edge**.

**Split-disciplined (train → validation), the decisive test:** no signal
survives. Signs flip across the split (US `momentum_3_1` +0.74 → −1.55; US
`low_volatility_60` −2.26 → −0.58), the lone train-"significant" result fails to
replicate and carries the wrong sign for its anomaly, and a 12-trial
multiple-testing haircut (≈2.23 expected best-of-N under noise) swallows it.
**It was not even worth opening the holdout.**

## 3. Why this is the *correct* place to stop (not a failure)

The discipline exists precisely to stop us from grinding more price-based signals
until one overfits. Classic technical factors on liquid large-caps are the most
arbitraged corner of the market; finding no edge there is the expected, honest
outcome. Continuing to mine the same OHLCV data for a "winner" would manufacture
a false positive, not discover alpha.

## 4. What a real edge would actually require (none of which we have yet)

1. **Point-in-time / survivorship-free data** — the current universe is
   current-constituents-only. The forward recorder fixes this *going forward*;
   a true backtest needs historical membership + delisting returns.
2. **Different information, not different math** — fundamentals, estimates,
   alt-data, supply-chain, text/news, or microstructure. OHLCV alone has been
   exhausted here.
   - **Fundamentals were tested (2026-06-27) — also NO edge.** The free-labor
     path won: built a SEC EDGAR XBRL point-in-time pipeline (`trader/data/edgar.py`,
     18yr history, actual filed dates → no look-ahead/restatement), fetched 497/503
     US names, and ran book-to-market & earnings-yield through the split-disciplined
     IC harness (R5). Result: book/market train −0.0054 → val +0.0105 (sign flip),
     earnings_yield ~0; neither significant. So the fundamental axis shows no edge
     on free data either. (yfinance's 5-quarter shallowness was bypassed entirely
     via EDGAR — depth was not the problem; there simply is no edge.)
   - **Disclosure-event metadata was tested (2026-08-10, R6) — also NO edge.**
     Built free point-in-time event pipelines (DART for KOSPI-200, EDGAR
     submissions 8-K/6-K for NASDAQ-100; 128k events, 5y, acceptance-date
     embargo) and ran 6 PRE-REGISTERED trailing-count signals (earnings 8-K,
     material agreements, all-events, 공급계약, 임원·주요주주 소유변동,
     대량보유변동) through the split-disciplined IC harness at h=21. Best
     train |t| = 0.94 vs noise-best ≈ 1.89 across N=6 — no trial passed the
     |t|≥2 gate, validation never opened, holdout stays locked. Caveats:
     n≈29 non-overlapping periods (5y span) limits power to |IC| ≳ 0.02, and
     only event COUNTS were tested — filing CONTENT (text/NLP) remains the
     one untested free axis.
   - **KR investor flows were tested (2026-08-16, R7) — also NO edge.** Built
     a free per-stock daily flow panel (Naver frgn backfill, 233,724 rows,
     KOSPI-200 × 5y, cross-validated exactly against KIS's investor API;
     KIS itself only serves 30 days) and ran 3 PRE-REGISTERED 7-day
     turnover-normalized imbalance signals (외국인 / 기관 / combined) at
     h=21. Best train |t| = 0.36 vs noise-best ≈ 1.48 across N=3 — nothing
     approached the gate, validation never opened, holdout locked. This is
     also the rigorous verdict on retail "매수/매도세" dashboard features:
     the underlying flow data has no cross-sectional 21d predictive power
     on this universe.
   - **Verdict across axes:** price/technical (R1–R2), breadth & multi-horizon,
     fundamentals (R5), disclosure-event metadata (R6), and investor flows
     (R7) — all rigorously split-tested, all NULL. The free-data edge ceiling
     is real and now quadruply confirmed (price, fundamentals, event metadata
     AND flows).
     A genuinely new edge would need PAID alt-data / microstructure, filing
     TEXT signals (unbuilt), or a different game (index beta + risk
     management, accepting no alpha).
3. **A different horizon/regime** — intraday or event-driven, where structure
   differs from the daily cross-section tested.
4. **Capacity-aware, costed, out-of-sample** validation of any candidate before
   a single dollar — the gate is built; nothing has passed it.

## 5. Honest one-liner

We built the machine that can tell the truth about edge, fed it clean broad data,
and it told us the truth: **there is no edge to trade in these signals.** The
value delivered is a trustworthy research/execution platform and a disciplined
*no* — plus a forward, survivorship-free data pipeline that could surface a real
edge later if fundamentally new information is added.

*See docs/data-limitations.md for data caveats; experiment log under experiments/
for the full trial record.*
