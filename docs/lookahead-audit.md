# Look-Ahead Audit — P0 Foundation

**Date:** 2026-06-16  
**Branch:** main  
**Scope:** All signal/indicator code, execution path, backtest/live engine loop

---

## 1. Timestamp Semantics Model

Our canonical event model:

| Time | Action |
|------|--------|
| Bar t closes | Data becomes available: OHLCV for bar t is finalised |
| Bar t close (same tick) | `on_bar(bar_t)` is called on all signal sources and `strategy.on_bar` |
| Bar t close (same tick) | Signal at bar t computed using closes ≤ bar t |
| Bar t close (same tick) | Order generated and submitted to `SimulatedExecutionHandler._pending` |
| Bar t+1 opens | `execution.on_bar(bar_t+1)` fires, fills the pending order at **bar t+1 open** |

This is the "signal-at-close, fill-at-next-open" model. It is the industry-standard
approach for daily bars. Using bar t's close in the signal computation is **correct
and not look-ahead** because bar t is already closed when the signal fires.

The only prohibited pattern is: using bar t's close as the **fill price** (i.e. filling
the same bar whose close generated the signal). `SimulatedExecutionHandler` structurally
prevents this — it only fills on the *next* call to `on_bar`.

---

## 2. Per-Signal Audit

### 2.1 TechnicalSignalSource (`trader/signals/technical.py`)

| Property | Value |
|----------|-------|
| Data availability | Bar t close (appended to deque on `on_bar`) |
| Decision time | Bar t close (same `on_bar` call) |
| Execution time | Bar t+1 open (SimulatedExecutionHandler) |
| Conclusion | **CLEAN** |

**How it works:** Maintains a `deque(maxlen=max(slow,60))` per `(market, ticker)` key.
On each `on_bar(bar_t)`, appends `bar.close` and computes MA/RSI/MACD/Bollinger using
only values already in the deque (i.e. bars ≤ t). No indexing into future bars.
The incremental rolling design means adding bars t+1, t+2 … never changes what was
computed at bar t.

### 2.2 MovingAverageCross (`trader/signals/indicators.py`)

| Property | Value |
|----------|-------|
| Data availability | Passed-in `bars` sequence (bars ≤ t from caller's deque) |
| Decision time | Bar t close |
| Execution time | Bar t+1 open |
| Conclusion | **CLEAN** |

**How it works:** Pure stateless frozen dataclass. `evaluate(bars)` uses
`closes = [b.close for b in bars]`, then `_sma(closes, fast)` and `_sma(closes, slow)`
which only look at `closes[-fast:]` and `closes[-slow:]` — i.e. the tail of the passed
window. No dependency on anything outside the passed sequence. Future bars never passed
by the caller.

### 2.3 RsiReversion (`trader/signals/indicators.py`)

| Property | Value |
|----------|-------|
| Data availability | Passed-in `bars` sequence (bars ≤ t) |
| Decision time | Bar t close |
| Execution time | Bar t+1 open |
| Conclusion | **CLEAN** |

**How it works:** `_rsi(closes)` uses `closes[i] - closes[i-1]` over the last
`period` differences — all within the provided sequence. No external state.

### 2.4 MacdTrend (`trader/signals/indicators.py`)

| Property | Value |
|----------|-------|
| Data availability | Passed-in `bars` sequence (bars ≤ t) |
| Decision time | Bar t close |
| Execution time | Bar t+1 open |
| Conclusion | **CLEAN** |

**How it works:** Builds a MACD time-series from the tail of the passed `closes`
(`tail = closes[-needed:]` where `needed = slow + signal - 1`). Iterates over
`range(signal)` windows entirely within that tail. No future data accessed.

### 2.5 BollingerReversion (`trader/signals/indicators.py`)

| Property | Value |
|----------|-------|
| Data availability | Passed-in `bars` sequence (bars ≤ t) |
| Decision time | Bar t close |
| Execution time | Bar t+1 open |
| Conclusion | **CLEAN** |

**How it works:** Uses `closes[-period:]` for the Bollinger window (all historical),
and `closes[-1]` as the current price — which is bar t's close (the most recent bar
in the passed sequence, i.e. bar t itself). This is correct: bar t is closed.

### 2.6 TechnicalIndicatorSource (`trader/signals/technical_indicator_source.py`)

| Property | Value |
|----------|-------|
| Data availability | Bar t close (appended to deque on `on_bar`) |
| Decision time | Bar t close |
| Execution time | Bar t+1 open |
| Conclusion | **CLEAN** |

**How it works:** Wrapper around any `TechnicalIndicator`. Maintains a
`deque(maxlen=max(window_size, indicator.min_bars))` per symbol. On `on_bar(bar_t)`,
appends `bar_t` then calls `indicator.evaluate(tuple(w))`. The tuple passed to
evaluate contains only bars ≤ t. Per-symbol isolation confirmed (separate deques
keyed by `(market, ticker)`).

### 2.7 FusionEngine (`trader/strategy/fusion_engine.py`) — sizing price note

| Property | Value |
|----------|-------|
| Signal uses | Bar t close (via sources) |
| `decide_orders` `price=bar.close` | Used only for **sizing** (shares = notional / price) |
| Fill price | Bar t+1 open (enforced by SimulatedExecutionHandler) |
| Conclusion | **CLEAN** |

**Key distinction:** `order_factory.orders_for_target(sized, portfolio, price=bar.close, ts=bar.ts)`
passes `bar.close` as a *sizing reference* (to convert a weight-based target into a share
count). The fill price is determined independently by `SimulatedExecutionHandler` as
`bar_{t+1}.open`. Sizing at close and filling at next open is standard practice and does
NOT constitute look-ahead — the sizing price is a proxy for "what price will we likely
trade at tomorrow" and is not the actual execution price.

If bar t+1 opens significantly different from bar t close, there is execution slippage,
but that is market risk, not look-ahead bias.

### 2.8 PortfolioVolTargeter (`trader/strategy/vol_target.py`)

| Property | Value |
|----------|-------|
| scalar() call | Returns EWMA var through bar t-1 only |
| update() call | Ingests bar t equity AFTER scalar() used for sizing |
| Conclusion | **CLEAN** |

**Protocol (enforced in FusionEngine.decide_orders):**
1. `s = vol_targeter.scalar()` — reads variance through yesterday
2. `sized.target_weight *= s` — applies scalar to today's order
3. `vol_targeter.update(portfolio.equity_krw())` — today's return enters EWMA

The ordering is explicit in the source code and confirmed by `test_vol_target.py::TestNoLookahead`.

### 2.9 momentum.py cross_sectional_momentum (`trader/research/momentum.py`)

| Property | Value |
|----------|-------|
| Signal date | `sorted_dates[rebal_idx - 1]` = last day of prior month |
| Data used for signal | `dates_up_to_signal = [d for d in sorted_dates if d <= signal_date]` |
| Execution date | `sorted_dates[rebal_idx]` = first day of new month |
| Conclusion | **CLEAN** |

**How it works:** The momentum score at `signal_date` uses:
- `near_date = sym_dates[-(skip+1)]` — 21 bars before signal_date within symbol's history
- `far_date = sym_dates[-(lookback+1)]` — 252 bars before signal_date

Both are strictly ≤ signal_date. The filter `d <= signal_date` is enforced explicitly.
Trades execute on `exec_date` (next trading day after signal_date). The `_period_return`
helper computes returns from `prev_signal_date` to `signal_date` — no future prices used.

Note: `_cost_fraction` uses `exec_date` prices for cost computation. This is correct:
costs are applied at execution time, not signal time.

### 2.10 BacktestEngine (`trader/backtest/engine.py`) + SimulatedExecutionHandler

| Property | Value |
|----------|-------|
| Event loop order | fills(bar_t) → mark(bar_t) → signals(bar_t) → submit_order |
| Fill timing | `on_bar(bar_t)` fills orders submitted on bar t-1, at `bar_t.open` |
| Same-bar fill | **Impossible by structure** |
| Conclusion | **CLEAN** |

**Loop invariant:** For any bar t:
1. `execution.on_bar(bar_t)` — fills pending orders (from bar t-1) at `bar_t.open`
2. `portfolio.mark(bar_t)` — marks positions at `bar_t.close`
3. `strategy.on_bar(bar_t)` — generates new orders using `bar_t.close` prices
4. `execution.submit_order(order)` — queues for bar t+1

An order generated in step 3 can never be filled in step 1 of the same iteration
because `submit_order` happens after `on_bar`. It will first appear in `_pending`
when step 1 runs in the *next* iteration (bar t+1).

LiveEngine (`trader/live/engine.py`) uses the identical loop structure. Parity confirmed.

---

## 3. Summary Table

| Component | Data window | Decision | Execution | Status |
|-----------|------------|----------|-----------|--------|
| TechnicalSignalSource | bars ≤ t | bar t close | bar t+1 open | CLEAN |
| MovingAverageCross | bars ≤ t | bar t close | bar t+1 open | CLEAN |
| RsiReversion | bars ≤ t | bar t close | bar t+1 open | CLEAN |
| MacdTrend | bars ≤ t | bar t close | bar t+1 open | CLEAN |
| BollingerReversion | bars ≤ t (close[-1] = bar t) | bar t close | bar t+1 open | CLEAN |
| TechnicalIndicatorSource | bars ≤ t | bar t close | bar t+1 open | CLEAN |
| FusionEngine (sizing) | bar t close (sizing only) | bar t close | bar t+1 open (fill) | CLEAN |
| PortfolioVolTargeter | equity through t-1 | scalar() before update() | — | CLEAN |
| momentum.py | dates ≤ signal_date | month-end | next trading day | CLEAN |
| BacktestEngine loop | — | bar t close | bar t+1 open (structural) | CLEAN |
| SimulatedExecutionHandler | — | — | bar t+1 open only | CLEAN |

**No look-ahead bugs were found.**

---

## 4. Risks and Observations (Not Bugs, but Worth Noting)

1. **Sizing slippage:** `order_factory` sizes using `bar.close` but fills at `bar_{t+1}.open`.
   In volatile markets these can differ significantly. This is correct behaviour but
   slippage is not currently modelled in `SimulatedExecutionHandler` (it uses `bar.open`
   exactly, with zero slippage around the open). A future improvement could add a
   configurable open-price slippage model.

2. **MacdTrend warmup uses full EMA not seeded EMA:** The `_ema` function initialises
   from `values[0]` and iterates forward. This is a simple EMA approximation — not
   a Wilder/seeded EMA. Consistent with `TechnicalSignalSource`'s same helper. No
   look-ahead, but results differ slightly from Pandas/TA-Lib MACD. Acceptable for
   this use case.

3. **momentum.py is RESEARCH ONLY:** The file has a clear docstring caveat
   (`RESEARCH / DIAGNOSTIC ONLY — never import from live, paper, or parity paths`).
   It has survivorship bias (hand-picked universe) and is not connected to any
   live or backtest signal path.

---

## 5. Test Coverage Added

`tests/test_lookahead_audit.py` adds:

- **Parametrized no-look-ahead invariant** over all 5 signal sources:
  `TechnicalSignalSource`, and `TechnicalIndicatorSource` wrapping each of
  `MovingAverageCross`, `RsiReversion`, `MacdTrend`, `BollingerReversion`.
  Verifies: signal at bar t from feed[:t+1] == signal at bar t from feed[:t+100].

- **SimulatedExecutionHandler same-bar fill prevention:** asserts that an order
  submitted at bar t's close cannot fill until bar t+1's open.

- **momentum.py no look-ahead:** verifies that injecting a future price spike after
  the first signal date does not change the first rebalance holdings.

- **FusionEngine vol-targeter call order:** asserts scalar() is read before
  update() in the decide_orders path (no same-day vol leak).
