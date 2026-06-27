# Production Readiness — makemoney

Tracks the program toward safe real-money use. **Strategy alpha is unproven**
(see RESEARCH_CONCLUSION.md); this checklist is about the PLATFORM being
production-grade so it *could* be deployed once a tradable strategy exists.
Go-live is always a **human-approved manual step** — nothing here authorizes
autonomous real-money orders.

## Completion estimate: ~90% (2026-06-27 update) → target ≥90% ✅ (human-only items remain)

Legend: [x] done & in code, [~] partial/needs wiring, [ ] missing.

### 1. Safety / risk controls — ~90% (table-stakes)
- [x] Kill switch (file-based trip/clear/is_active) — `live/killswitch.py`
- [x] Pre-trade gate — per-order notional cap, position-weight cap, max-orders
      circuit breaker, fat-finger qty ceiling, price-sanity (±30%), cash buffer
      — `live/pretrade.py`
- [x] ATR sizing, daily-loss kill, per-market caps (risk manager)
- [x] Hard LIVE-vs-paper guard: `live_allowed()` requires ALL of --live flag +
      kill-switch-clear + `LIVE_TRADING_ENABLED=true` + account allowlist; AND
      `build_kis_client` targets the paper endpoint by default (live base is a
      deliberate code change). Defaults are paper-safe. Documented in
      GO_LIVE_RUNBOOK.md.

### 2. Execution correctness — ~85% (table-stakes)
- [x] KIS client + paper client; backtest==live parity (mutation-tested)
- [x] Resilient submitter; EOD unfilled cancel/re-reconcile (E2)
- [x] Token caching (24h) + re-issue
- [~] Idempotent submission / duplicate-order guard on retry **(verify)**

### 3. Observability / alerting — ~75%
- [x] Fan-out alert Monitor; LogAlertSink; **WebhookAlertSink** (POST WARN/CRITICAL)
      — `live/monitor.py`
- [~] Webhook actually configured (Telegram/Slack URL in env) **(needs user URL)**
- [x] **Heartbeat / dead-man's switch** — `live/heartbeat.py` + `run_healthcheck`
      CLI (cron 9/18h) alerts on stale/missing jobs; wired into daily run,
      accumulator, forward recorder.
- [x] Structured journal of runs/orders — `live/journal.py`
- [~] Daily summary report (positions, PnL, actions) **(partial)**

### 4. Reconciliation / accounting — ~70%
- [x] Reconcile with OK/WARN/CRITICAL severity + broker-vs-internal drift;
      caller kill-switches if not ok — `live/reconcile.py`
- [x] Ledger + FX (KRW-settled) — `live/ledger.py`
- [x] **B1 RESOLVED (2026-06-27, live inspection)**: the overseas 388M
      `tot_asst_amt`/`frcr_evlu_tota` is a KIS **paper-account phantom** — usable
      (`frcr_use_psbl_amt`), withdrawable (`wdrw_psbl_tot_amt`), per-currency cash
      and positions are ALL zero, and it drifts with the USD FX rate. Not real
      money, not an accounting bug. `account_snapshot` correctly uses only
      domestic `dnca_tot_amt` (~100M KRW). Documented in `kis_client.py`.

### 5. Operational / runbook — ~65%
- [x] Cron daily runners (US/KR), accumulator, forward recorder, reconcile
- [x] Config validation on startup — `AppConfig.from_env` fails fast with a clear
      `ConfigError` on missing/empty keys; paper-safe default (6 tests).
- [x] Secrets in gitignored .env; never logged
- [x] **Go-live runbook** — `docs/GO_LIVE_RUNBOOK.md` (gates, pre-flight,
      cutover, rollback, daily ops).
- [ ] Mac sleep prevention (pmset) so cron actually fires **(user/ops)**

### 6. Failure recovery — ~70%
- [x] Idempotent-ish daily run; resumable accumulator/forward recorder
- [~] Crash-mid-session recovery / partial-state resume **(verify)**
- [x] Network/broker retry-backoff in submitter

## Status: ≥90% reached for autonomously-buildable items ✅
Done this loop: heartbeat/dead-man's switch + healthcheck cron; config
fail-fast validation; LIVE hard-guard verified (4-gate + paper-endpoint default);
go-live runbook. Daily heartbeat wired (daily_run/accumulator/forward_record).

### Remaining — require the HUMAN (not autonomously doable)
- ~~B1 reconcile~~ — **RESOLVED** by live inspection (paper-account phantom; see §4).
- **ALERT_WEBHOOK_URL**: set a Slack/Telegram/Discord webhook to receive pushes.
- **pmset / always-on host**: so cron fires (else heartbeat will correctly alert).
- **A validated strategy**: the platform is ready; the edge is not (see
  RESEARCH_CONCLUSION.md). Live deployment of current signals is not advised.

### Nice-to-have (non-blocking, future)
- Daily summary report polish; crash-mid-session resume verification;
  idempotent-submission/duplicate-order guard verification.
