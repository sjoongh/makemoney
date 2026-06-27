# Production Readiness — makemoney

Tracks the program toward safe real-money use. **Strategy alpha is unproven**
(see RESEARCH_CONCLUSION.md); this checklist is about the PLATFORM being
production-grade so it *could* be deployed once a tradable strategy exists.
Go-live is always a **human-approved manual step** — nothing here authorizes
autonomous real-money orders.

## Completion estimate: ~80% → target ≥90%

Legend: [x] done & in code, [~] partial/needs wiring, [ ] missing.

### 1. Safety / risk controls — ~90% (table-stakes)
- [x] Kill switch (file-based trip/clear/is_active) — `live/killswitch.py`
- [x] Pre-trade gate — per-order notional cap, position-weight cap, max-orders
      circuit breaker, fat-finger qty ceiling, price-sanity (±30%), cash buffer
      — `live/pretrade.py`
- [x] ATR sizing, daily-loss kill, per-market caps (risk manager)
- [~] Hard LIVE-vs-paper guard: confirm a single explicit flag gates real orders
      and defaults to paper. **(verify/strengthen)**

### 2. Execution correctness — ~85% (table-stakes)
- [x] KIS client + paper client; backtest==live parity (mutation-tested)
- [x] Resilient submitter; EOD unfilled cancel/re-reconcile (E2)
- [x] Token caching (24h) + re-issue
- [~] Idempotent submission / duplicate-order guard on retry **(verify)**

### 3. Observability / alerting — ~75%
- [x] Fan-out alert Monitor; LogAlertSink; **WebhookAlertSink** (POST WARN/CRITICAL)
      — `live/monitor.py`
- [~] Webhook actually configured (Telegram/Slack URL in env) **(needs user URL)**
- [ ] **Heartbeat / dead-man's switch** — alert if a scheduled run did NOT fire
      (the #1 risk here: Mac sleeps → cron silently misses). **(BUILD — top gap)**
- [x] Structured journal of runs/orders — `live/journal.py`
- [~] Daily summary report (positions, PnL, actions) **(partial)**

### 4. Reconciliation / accounting — ~70%
- [x] Reconcile with OK/WARN/CRITICAL severity + broker-vs-internal drift;
      caller kill-switches if not ok — `live/reconcile.py`
- [x] Ledger + FX (KRW-settled) — `live/ledger.py`
- [ ] **B1 unresolved**: overseas account 383M present-balance vs 0 positions/cash
      discrepancy — needs broker clarification before trusting overseas equity.
      Currently conservative (domestic KRW cash only). **(human/broker)**

### 5. Operational / runbook — ~65%
- [x] Cron daily runners (US/KR), accumulator, forward recorder, reconcile
- [~] Config validation on startup (fail-fast on bad/missing config) **(thin — harden)**
- [x] Secrets in gitignored .env; never logged
- [ ] **Go-live runbook** — paper→live cutover steps, pre-flight checklist,
      rollback. **(write)**
- [ ] Mac sleep prevention (pmset) so cron actually fires **(user/ops)**

### 6. Failure recovery — ~70%
- [x] Idempotent-ish daily run; resumable accumulator/forward recorder
- [~] Crash-mid-session recovery / partial-state resume **(verify)**
- [x] Network/broker retry-backoff in submitter

## Plan to reach ≥90% (autonomous, no real orders)
1. Heartbeat / dead-man's switch + healthcheck CLI + cron alert. ← next
2. Startup config validation (fail-fast) + LIVE-flag hard guard verification.
3. Go-live runbook doc.
4. Daily summary report polish.
(B1 and webhook URL and pmset require the human; flagged, not blocking.)
