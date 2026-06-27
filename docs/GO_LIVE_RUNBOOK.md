# Go-Live Runbook — makemoney

> **Read this in full before any real-money use.** Going live is a deliberate,
> human-performed procedure. Nothing in the codebase places real-money orders
> autonomously, and **no strategy edge has been proven** (see
> RESEARCH_CONCLUSION.md) — going live with the current signals is NOT advised
> on expected-value grounds. This runbook exists so that *if/when* a validated
> strategy exists, the cutover is safe.

## 0. Hard prerequisites (do not skip)
- A strategy that passed the full disciplined gate (train→val→**holdout**,
  positive after costs). **Not currently the case.**
- A funded, dedicated KIS account you can afford to lose entirely.
- Push alerting configured: set `ALERT_WEBHOOK_URL` (Slack/Telegram/Discord).
- `pmset` (or always-on host) so cron actually fires; heartbeat healthcheck green.

## 1. The live gates (all must pass — see `trader/app/run_daily.py:live_allowed`)
Live order submission is blocked unless ALL of:
1. `--live` flag passed to the runner (default is dry-run).
2. Kill switch inactive (`.kill_switch.json`).
3. `LIVE_TRADING_ENABLED=true` in env.
4. Account is in `KIS_LIVE_ACCOUNT_ALLOWLIST` (comma-separated).

Additionally, `build_kis_client()` currently targets the **paper endpoint**
(`PAPER_BASE`) by design. **Wiring a real-money base URL is itself a deliberate
code change** and the final human gate — until then the system physically
cannot reach the live endpoint.

## 2. Pre-flight checklist (run each go-live day)
- [ ] `python -m trader.app.run_healthcheck` → OK (no stale jobs)
- [ ] `python -m trader.app.run_reconcile` → no CRITICAL drift. (B1 resolved: the
      overseas 388M is a paper phantom; on a REAL account fold only usable foreign
      cash `frcr_dncl_amt_2`, never `tot_asst_amt` — see kis_client.account_snapshot)
- [ ] Kill switch clear; pre-trade limits sane (`PreTradeLimits`:
      max_order_notional_krw, max_position_weight, max_orders_per_run, fat_finger_qty)
- [ ] Account balance matches expectation; FX rate fresh
- [ ] Start with the **smallest possible size** (1 share / minimum notional)

## 3. Cutover (paper → live)
1. Run paper-forward for a meaningful period; confirm journal/reconcile clean.
2. Set `LIVE_TRADING_ENABLED=true` and `KIS_LIVE_ACCOUNT_ALLOWLIST=<acct>`.
3. Wire `LIVE_BASE` in the client factory (deliberate code change + review).
4. First live run with `--live` at minimum size; watch the journal + alerts live.
5. Reconcile immediately after; verify broker positions == internal ledger.

## 4. Rollback / kill
- `KillSwitch().trip(reason=..., source="operator")` (or write `.kill_switch.json`)
  → blocks all further live submission immediately.
- Revert `LIVE_TRADING_ENABLED`; remove account from allowlist.
- Cancel open orders via the reconcile/cancel path; reconcile to flat.

## 5. Daily operations
- Cron: daily runners (US/KR), accumulator, forward recorder, reconcile,
  healthcheck (dead-man's switch). All log under `logs/`.
- Watch for `HEARTBEAT_STALE` (job didn't fire) and any `CRITICAL` reconcile alert.
- Weekly: review journal + PnL; monthly: re-validate the strategy on fresh data.

## 6. Honest reminder
The platform is production-grade; the **edge is not**. Treat any live deployment
of the current signals as paying tuition, not investing. Revisit only with a
strategy that cleared the holdout after costs, or a fundamentally new data axis.
