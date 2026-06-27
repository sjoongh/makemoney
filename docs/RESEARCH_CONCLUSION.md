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
   - **Verdict across axes:** price/technical (R1–R2), breadth & multi-horizon,
     and fundamentals (R5) — all rigorously split-tested, all NULL. The free-data
     edge ceiling is real and now doubly confirmed (price AND fundamentals).
     A genuinely new edge would need PAID alt-data / microstructure, or a
     different game (index beta + risk management, accepting no alpha).
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
