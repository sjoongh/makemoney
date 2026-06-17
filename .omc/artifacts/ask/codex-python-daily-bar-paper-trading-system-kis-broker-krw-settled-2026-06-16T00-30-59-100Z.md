# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-16T00:30:59.101Z

## Original task

Python daily-bar paper-trading system (KIS broker, KRW-settled, deterministic event engine, run_daily once/day, RunLedger idempotency, RiskManager with kill-switch+daily-loss-limit, SignalJournal). I'm hardening it for eventual REAL-money use. List the ESSENTIAL safety/operational components in PRIORITY ORDER for a once-daily (not HFT) retail system, and for each: what it does + minimal deterministic-friendly design. Cover at least:
- order submission failure handling (retries w/ backoff, idempotency to avoid double-submit on retry, distinguishing transient vs terminal errors)
- partial fill / unfilled order handling (order didn't fully fill by EOD — cancel? carry? our sim assumes full next-open fill)
- order reconciliation (did the order actually fill? confirm via fill inquiry before updating state — we already do fills-only portfolio updates)
- pre-trade risk checks at submission time (max order notional, max position, buying-power/cash check, fat-finger qty guard, price sanity vs last close)
- monitoring/alerting (what to alert on: order rejects, kill-switch trips, daily loss breach, no-data/stale-bar, fill mismatch) and a simple channel (log + optional webhook)
- anomaly auto-kill (conditions that should halt trading automatically)
- a 'dry-run/live' safety gate + 'max orders per run' circuit breaker

Give priority order (P0/P1/P2) and a terse minimal design per item. Mark which are essential BEFORE any real money vs nice-to-have. Senior, terse, no fluff.

## Final prompt

Python daily-bar paper-trading system (KIS broker, KRW-settled, deterministic event engine, run_daily once/day, RunLedger idempotency, RiskManager with kill-switch+daily-loss-limit, SignalJournal). I'm hardening it for eventual REAL-money use. List the ESSENTIAL safety/operational components in PRIORITY ORDER for a once-daily (not HFT) retail system, and for each: what it does + minimal deterministic-friendly design. Cover at least:
- order submission failure handling (retries w/ backoff, idempotency to avoid double-submit on retry, distinguishing transient vs terminal errors)
- partial fill / unfilled order handling (order didn't fully fill by EOD — cancel? carry? our sim assumes full next-open fill)
- order reconciliation (did the order actually fill? confirm via fill inquiry before updating state — we already do fills-only portfolio updates)
- pre-trade risk checks at submission time (max order notional, max position, buying-power/cash check, fat-finger qty guard, price sanity vs last close)
- monitoring/alerting (what to alert on: order rejects, kill-switch trips, daily loss breach, no-data/stale-bar, fill mismatch) and a simple channel (log + optional webhook)
- anomaly auto-kill (conditions that should halt trading automatically)
- a 'dry-run/live' safety gate + 'max orders per run' circuit breaker

Give priority order (P0/P1/P2) and a terse minimal design per item. Mark which are essential BEFORE any real money vs nice-to-have. Senior, terse, no fluff.

## Raw output

```text
Below is the priority order I’d use for a once-daily retail system before allowing real KRW capital. This is engineering/risk-control guidance, not investment advice. Broker APIs commonly expose order, cancel, order-history, and fill inquiry surfaces; KIS/OpenAPI wrappers document those categories, and industry risk-control guidance consistently emphasizes pre-trade controls, post-trade checks, kill switches, and monitoring. Sources: [KIS OpenAPI wrapper docs](https://cran.r-project.org/web/packages/kisopenapi/kisopenapi.pdf), [KIS API portal reference pointer](https://apiportal.koreainvestment.com/), [FIA automated trading risk controls](https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf), [SEC order execution overview](https://www.sec.gov/files/staff-report-equity-options-market-struction-conditions-early-2021.pdf).

**P0: Essential Before Real Money**

1. **Live/Dry-Run Safety Gate**
   - What: Prevent accidental real orders.
   - Minimal design: `mode in {"dry_run", "live"}` from explicit config, not CLI default. Live requires `LIVE_TRADING_ENABLED=true`, account allowlist, broker account type check, and startup banner persisted to `RunLedger`.
   - Deterministic: mode becomes part of `RunContext`; every event records `mode`.

2. **RunLedger Idempotency**
   - What: Prevent duplicate run/order effects after crash, retry, or rerun.
   - Minimal design: unique key: `(trade_date, strategy_id, account_id, phase)`. For each intended order, generate stable `client_order_key = hash(trade_date, strategy, symbol, side, target_qty, signal_id)`.
   - Deterministic: append-only states: `INTENDED -> SUBMITTING -> SUBMITTED -> ACKED -> FILLED/PARTIAL/CANCELLED/REJECTED/UNKNOWN`.

3. **Pre-Trade Risk Checks at Submission Time**
   - What: Block bad orders before broker submission.
   - Minimal design: synchronous `RiskManager.approve(order, portfolio, cash, market_snapshot)`.
   - Required checks:
     - max order notional
     - max total daily notional
     - max position notional / shares / portfolio weight
     - cash/buying-power check with fee/tax buffer
     - fat-finger quantity guard vs planned target
     - price sanity vs last close, e.g. reject if reference price missing or implied limit/open price deviates beyond threshold
     - no shorting unless explicitly supported
     - symbol allowlist / market status check
   - Deterministic: returns structured `APPROVED` or `BLOCKED(reason_code)`; never mutates state.

4. **Max Orders Per Run Circuit Breaker**
   - What: Stop runaway daily rebalance or corrupted signal fanout.
   - Minimal design: hard cap, e.g. `max_orders_per_run`, `max_symbols_changed`, `max_turnover_pct`.
   - Deterministic: evaluated before first submission; if breached, write `RUN_HALTED_TOO_MANY_ORDERS`.

5. **Order Submission Failure Handling**
   - What: Avoid both missed orders and double-submit.
   - Minimal design:
     - classify broker/API errors into `TRANSIENT`, `TERMINAL`, `UNKNOWN`.
     - transient: retry with bounded exponential backoff + jitter, e.g. 3 attempts.
     - terminal: no retry; mark rejected with broker code.
     - unknown timeout: do not blindly resubmit. First query order history/open orders/fills using `client_order_key` or broker timestamp/symbol/side/qty window.
   - Idempotency: retry only same logical order; persist attempt before HTTP call as `SUBMITTING`.
   - Deterministic: retries are deterministic in count/state; wall-clock delay does not change decision outcome.

6. **Order Reconciliation Before Portfolio Mutation**
   - What: State changes only reflect confirmed executions.
   - Minimal design: after submission, query broker fills/order history. Portfolio update consumes only confirmed fills, not order ACKs.
   - Required invariant: `PortfolioState(t+1) = PortfolioState(t) + confirmed_fills`.
   - Deterministic: persist raw broker fill records; normalize into internal `FillEvent`.

7. **Partial Fill / Unfilled EOD Policy**
   - What: Handle reality diverging from “full next-open fill” sim assumption.
   - Minimal design for daily bars: default to **cancel unfilled residual by EOD** unless strategy explicitly supports carry.
   - States:
     - `FILLED`: update by fills.
     - `PARTIAL`: update filled qty, cancel residual, record slippage/missed qty.
     - `UNFILLED`: cancel, no portfolio mutation.
     - `CANCEL_FAILED`: auto-kill next run until manually reconciled.
   - Deterministic: one policy flag: `eod_unfilled_policy = "cancel"` initially. Add `"carry"` only after strategy/backtest semantics support open orders.

8. **Kill Switch**
   - What: Halt all new trading under unsafe conditions.
   - Minimal design: durable `kill_switch_active` flag with reason, timestamp, source.
   - Trips:
     - daily loss limit breached
     - broker reconciliation mismatch
     - unknown order state after retries/inquiry
     - cancel failure
     - duplicate live order detection
     - stale/no data
     - cash/position mismatch beyond tolerance
   - Deterministic: checked at run start and before every submit.

9. **Daily Loss Limit**
   - What: Stop trading after abnormal realized/unrealized loss.
   - Minimal design: compute daily PnL from broker-confirmed positions and prior close equity. If loss <= `-limit`, halt new buys and optionally allow only risk-reducing sells.
   - Deterministic: use one timestamped broker snapshot plus configured reference prices.

10. **Monitoring / Alerting**
   - What: Human gets notified when automation is unsafe.
   - Minimal design: structured log always; optional webhook for severity `WARN+`.
   - Alert on:
     - order reject
     - transient retry exhausted
     - unknown order state
     - partial/unfilled at EOD
     - cancel failure
     - kill-switch trip
     - daily loss breach
     - stale/no bar
     - fill mismatch
     - cash/position reconciliation mismatch
     - live mode start/end summary
   - Deterministic: alert payload uses event IDs from `RunLedger`; duplicate suppression by event ID.

**P1: Strongly Recommended Before Meaningful Capital**

11. **Broker Account Reconciliation**
   - What: Confirm internal state equals broker truth.
   - Minimal design: before run and after run, fetch cash, holdings, open orders, fills. Compare to internal ledger with tolerances.
   - Failure: halt new orders until reconciled.

12. **Open Order Sweep**
   - What: Avoid forgotten orders from prior runs/manual actions.
   - Minimal design: at run start, query open orders. If any unmanaged order exists, halt or cancel according to policy.
   - Deterministic: unmanaged means no matching `client_order_key` in ledger.

13. **Data Freshness and Corporate Action Guard**
   - What: Prevent trading on stale/split-adjustment-bad data.
   - Minimal design: require latest bar date equals expected market date; reject if OHLCV missing, zero, extreme gap, or adjusted/unadjusted source changed unexpectedly.
   - Failure: no trade for affected symbols or full halt.

14. **SignalJournal Immutability**
   - What: Reproduce why an order existed.
   - Minimal design: persist input bars hash, signal values, target weights, risk decisions, generated orders, and code/config version.
   - Deterministic: journal is append-only and referenced by order IDs.

15. **Manual Override Procedure**
   - What: Safe human intervention.
   - Minimal design: CLI commands: `status`, `activate-kill`, `clear-kill`, `reconcile`, `cancel-open-orders`. Clearing kill switch requires reason text and fresh reconciliation.

16. **Config Limits as Code**
   - What: Avoid hidden production behavior.
   - Minimal design: versioned `risk_limits.yaml`; validate schema; persist config hash per run.
   - Failure: invalid/missing limit means halt, not default-to-large.

**P2: Nice-To-Have / Later Hardening**

17. **Shadow Broker / Paper-Live Diff**
   - What: Compare dry-run expected orders against live inquiry snapshots before enabling capital.
   - Minimal design: run live data + dry orders for N days; alert on mismatches.

18. **Replay Harness**
   - What: Prove deterministic event behavior.
   - Minimal design: replay `SignalJournal + BrokerEvents` and assert same ledger states.

19. **Webhook Escalation Ladder**
   - What: Better ops response.
   - Minimal design: log -> webhook -> SMS/email for P0 events.

20. **Post-Trade Analytics**
   - What: Detect degradation.
   - Minimal design: track slippage, partial-fill rate, reject rate, missed trades, realized fees/taxes.

21. **Separate Permissions / Account Segregation**
   - What: Limit blast radius.
   - Minimal design: dedicated account/subaccount, no margin, no derivatives, capped cash balance, withdrawal/trading permissions separated where broker supports it.

**Minimum Real-Money Bar**

Do not go live until these exist and are tested against broker paper/mock/live-inquiry flows:

- dry/live explicit gate
- durable RunLedger idempotency
- pre-trade risk checks
- max orders per run
- retry/error classification with no blind resubmit
- fill inquiry before portfolio update
- EOD partial/unfilled policy
- kill switch
- daily loss limit
- stale data halt
- structured alerts
- broker reconciliation before and after run

For your architecture, the key rule is: **orders may be intended from signals, but portfolio state may only move from broker-confirmed fills.**


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019ecdd5-eca8-7f60-93d6-6fe359ec8e4e
--------
user
Python daily-bar paper-trading system (KIS broker, KRW-settled, deterministic event engine, run_daily once/day, RunLedger idempotency, RiskManager with kill-switch+daily-loss-limit, SignalJournal). I'm hardening it for eventual REAL-money use. List the ESSENTIAL safety/operational components in PRIORITY ORDER for a once-daily (not HFT) retail system, and for each: what it does + minimal deterministic-friendly design. Cover at least:
- order submission failure handling (retries w/ backoff, idempotency to avoid double-submit on retry, distinguishing transient vs terminal errors)
- partial fill / unfilled order handling (order didn't fully fill by EOD — cancel? carry? our sim assumes full next-open fill)
- order reconciliation (did the order actually fill? confirm via fill inquiry before updating state — we already do fills-only portfolio updates)
- pre-trade risk checks at submission time (max order notional, max position, buying-power/cash check, fat-finger qty guard, price sanity vs last close)
- monitoring/alerting (what to alert on: order rejects, kill-switch trips, daily loss breach, no-data/stale-bar, fill mismatch) and a simple channel (log + optional webhook)
- anomaly auto-kill (conditions that should halt trading automatically)
- a 'dry-run/live' safety gate + 'max orders per run' circuit breaker

Give priority order (P0/P1/P2) and a terse minimal design per item. Mark which are essential BEFORE any real money vs nice-to-have. Senior, terse, no fluff.
codex
I’ll verify a couple of current broker/API and operational-risk references, then keep the answer focused on deterministic design rather than market advice.
web search: 
web search: Korea Investment Securities Open API order inquiry fill cancel documentation
codex
Below is the priority order I’d use for a once-daily retail system before allowing real KRW capital. This is engineering/risk-control guidance, not investment advice. Broker APIs commonly expose order, cancel, order-history, and fill inquiry surfaces; KIS/OpenAPI wrappers document those categories, and industry risk-control guidance consistently emphasizes pre-trade controls, post-trade checks, kill switches, and monitoring. Sources: [KIS OpenAPI wrapper docs](https://cran.r-project.org/web/packages/kisopenapi/kisopenapi.pdf), [KIS API portal reference pointer](https://apiportal.koreainvestment.com/), [FIA automated trading risk controls](https://www.fia.org/sites/default/files/2024-07/FIA_WP_AUTOMATED%20TRADING%20RISK%20CONTROLS_FINAL_0.pdf), [SEC order execution overview](https://www.sec.gov/files/staff-report-equity-options-market-struction-conditions-early-2021.pdf).

**P0: Essential Before Real Money**

1. **Live/Dry-Run Safety Gate**
   - What: Prevent accidental real orders.
   - Minimal design: `mode in {"dry_run", "live"}` from explicit config, not CLI default. Live requires `LIVE_TRADING_ENABLED=true`, account allowlist, broker account type check, and startup banner persisted to `RunLedger`.
   - Deterministic: mode becomes part of `RunContext`; every event records `mode`.

2. **RunLedger Idempotency**
   - What: Prevent duplicate run/order effects after crash, retry, or rerun.
   - Minimal design: unique key: `(trade_date, strategy_id, account_id, phase)`. For each intended order, generate stable `client_order_key = hash(trade_date, strategy, symbol, side, target_qty, signal_id)`.
   - Deterministic: append-only states: `INTENDED -> SUBMITTING -> SUBMITTED -> ACKED -> FILLED/PARTIAL/CANCELLED/REJECTED/UNKNOWN`.

3. **Pre-Trade Risk Checks at Submission Time**
   - What: Block bad orders before broker submission.
   - Minimal design: synchronous `RiskManager.approve(order, portfolio, cash, market_snapshot)`.
   - Required checks:
     - max order notional
     - max total daily notional
     - max position notional / shares / portfolio weight
     - cash/buying-power check with fee/tax buffer
     - fat-finger quantity guard vs planned target
     - price sanity vs last close, e.g. reject if reference price missing or implied limit/open price deviates beyond threshold
     - no shorting unless explicitly supported
     - symbol allowlist / market status check
   - Deterministic: returns structured `APPROVED` or `BLOCKED(reason_code)`; never mutates state.

4. **Max Orders Per Run Circuit Breaker**
   - What: Stop runaway daily rebalance or corrupted signal fanout.
   - Minimal design: hard cap, e.g. `max_orders_per_run`, `max_symbols_changed`, `max_turnover_pct`.
   - Deterministic: evaluated before first submission; if breached, write `RUN_HALTED_TOO_MANY_ORDERS`.

5. **Order Submission Failure Handling**
   - What: Avoid both missed orders and double-submit.
   - Minimal design:
     - classify broker/API errors into `TRANSIENT`, `TERMINAL`, `UNKNOWN`.
     - transient: retry with bounded exponential backoff + jitter, e.g. 3 attempts.
     - terminal: no retry; mark rejected with broker code.
     - unknown timeout: do not blindly resubmit. First query order history/open orders/fills using `client_order_key` or broker timestamp/symbol/side/qty window.
   - Idempotency: retry only same logical order; persist attempt before HTTP call as `SUBMITTING`.
   - Deterministic: retries are deterministic in count/state; wall-clock delay does not change decision outcome.

6. **Order Reconciliation Before Portfolio Mutation**
   - What: State changes only reflect confirmed executions.
   - Minimal design: after submission, query broker fills/order history. Portfolio update consumes only confirmed fills, not order ACKs.
   - Required invariant: `PortfolioState(t+1) = PortfolioState(t) + confirmed_fills`.
   - Deterministic: persist raw broker fill records; normalize into internal `FillEvent`.

7. **Partial Fill / Unfilled EOD Policy**
   - What: Handle reality diverging from “full next-open fill” sim assumption.
   - Minimal design for daily bars: default to **cancel unfilled residual by EOD** unless strategy explicitly supports carry.
   - States:
     - `FILLED`: update by fills.
     - `PARTIAL`: update filled qty, cancel residual, record slippage/missed qty.
     - `UNFILLED`: cancel, no portfolio mutation.
     - `CANCEL_FAILED`: auto-kill next run until manually reconciled.
   - Deterministic: one policy flag: `eod_unfilled_policy = "cancel"` initially. Add `"carry"` only after strategy/backtest semantics support open orders.

8. **Kill Switch**
   - What: Halt all new trading under unsafe conditions.
   - Minimal design: durable `kill_switch_active` flag with reason, timestamp, source.
   - Trips:
     - daily loss limit breached
     - broker reconciliation mismatch
     - unknown order state after retries/inquiry
     - cancel failure
     - duplicate live order detection
     - stale/no data
     - cash/position mismatch beyond tolerance
   - Deterministic: checked at run start and before every submit.

9. **Daily Loss Limit**
   - What: Stop trading after abnormal realized/unrealized loss.
   - Minimal design: compute daily PnL from broker-confirmed positions and prior close equity. If loss <= `-limit`, halt new buys and optionally allow only risk-reducing sells.
   - Deterministic: use one timestamped broker snapshot plus configured reference prices.

10. **Monitoring / Alerting**
   - What: Human gets notified when automation is unsafe.
   - Minimal design: structured log always; optional webhook for severity `WARN+`.
   - Alert on:
     - order reject
     - transient retry exhausted
     - unknown order state
     - partial/unfilled at EOD
     - cancel failure
     - kill-switch trip
     - daily loss breach
     - stale/no bar
     - fill mismatch
     - cash/position reconciliation mismatch
     - live mode start/end summary
   - Deterministic: alert payload uses event IDs from `RunLedger`; duplicate suppression by event ID.

**P1: Strongly Recommended Before Meaningful Capital**

11. **Broker Account Reconciliation**
   - What: Confirm internal state equals broker truth.
   - Minimal design: before run and after run, fetch cash, holdings, open orders, fills. Compare to internal ledger with tolerances.
   - Failure: halt new orders until reconciled.

12. **Open Order Sweep**
   - What: Avoid forgotten orders from prior runs/manual actions.
   - Minimal design: at run start, query open orders. If any unmanaged order exists, halt or cancel according to policy.
   - Deterministic: unmanaged means no matching `client_order_key` in ledger.

13. **Data Freshness and Corporate Action Guard**
   - What: Prevent trading on stale/split-adjustment-bad data.
   - Minimal design: require latest bar date equals expected market date; reject if OHLCV missing, zero, extreme gap, or adjusted/unadjusted source changed unexpectedly.
   - Failure: no trade for affected symbols or full halt.

14. **SignalJournal Immutability**
   - What: Reproduce why an order existed.
   - Minimal design: persist input bars hash, signal values, target weights, risk decisions, generated orders, and code/config version.
   - Deterministic: journal is append-only and referenced by order IDs.

15. **Manual Override Procedure**
   - What: Safe human intervention.
   - Minimal design: CLI commands: `status`, `activate-kill`, `clear-kill`, `reconcile`, `cancel-open-orders`. Clearing kill switch requires reason text and fresh reconciliation.

16. **Config Limits as Code**
   - What: Avoid hidden production behavior.
   - Minimal design: versioned `risk_limits.yaml`; validate schema; persist config hash per run.
   - Failure: invalid/missing limit means halt, not default-to-large.

**P2: Nice-To-Have / Later Hardening**

17. **Shadow Broker / Paper-Live Diff**
   - What: Compare dry-run expected orders against live inquiry snapshots before enabling capital.
   - Minimal design: run live data + dry orders for N days; alert on mismatches.

18. **Replay Harness**
   - What: Prove deterministic event behavior.
   - Minimal design: replay `SignalJournal + BrokerEvents` and assert same ledger states.

19. **Webhook Escalation Ladder**
   - What: Better ops response.
   - Minimal design: log -> webhook -> SMS/email for P0 events.

20. **Post-Trade Analytics**
   - What: Detect degradation.
   - Minimal design: track slippage, partial-fill rate, reject rate, missed trades, realized fees/taxes.

21. **Separate Permissions / Account Segregation**
   - What: Limit blast radius.
   - Minimal design: dedicated account/subaccount, no margin, no derivatives, capped cash balance, withdrawal/trading permissions separated where broker supports it.

**Minimum Real-Money Bar**

Do not go live until these exist and are tested against broker paper/mock/live-inquiry flows:

- dry/live explicit gate
- durable RunLedger idempotency
- pre-trade risk checks
- max orders per run
- retry/error classification with no blind resubmit
- fill inquiry before portfolio update
- EOD partial/unfilled policy
- kill switch
- daily loss limit
- stale data halt
- structured alerts
- broker reconciliation before and after run

For your architecture, the key rule is: **orders may be intended from signals, but portfolio state may only move from broker-confirmed fills.**
tokens used
8,574

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
