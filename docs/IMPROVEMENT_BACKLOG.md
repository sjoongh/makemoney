# Improvement Backlog — makemoney

Source: 2026-07-05 exhaustive multi-agent improvement audit (44 agents, 7
dimensions, each candidate adversarially vetted for real-value & fantasy-alpha).
**No P0. No fantasy-alpha candidates survived vetting.** The whole backlog raises
correctness / reliability / honesty / usability — **none of it moves the alpha
needle, because there is none to move** (see RESEARCH_CONCLUSION.md).

Status key: ✅ done · ⏳ needs user input · ▫ open

## P1 — live/honesty-critical, cheap-to-moderate

- ⏳ **Configure `ALERT_WEBHOOK_URL`** (Slack/Telegram/Discord) — code wired+tested
  (`run_healthcheck.py`); today all alerts are log-only. **User must supply a
  webhook URL.** Keystone: everything else monitoring-related is half-dead until set.
- ⏳ **External dead-man ping** (healthchecks.io / cronitor) from healthcheck's
  success branch — the Mac-asleep failure is structurally undetectable in-band.
  **User must create a free monitor + paste its ping URL.**
- ⏳ **Back up the live ledger `beta_kis_track.jsonl`** — currently single-copy on
  one Mac. NOTE: **the GitHub repo is PUBLIC**, so `git add -f` would publish your
  paper trading activity (order ids, equity, positions — no credentials). **User
  decision:** make repo private / use a private backup / accept public / leave as-is.
- ✅ **`tests/test_run_beta_kis_paper.py`** — money-path guard coverage (done 07-05).
- ✅ **Dashboard 'today's decision' card incl. HOLD** (done 07-05).
- ✅ **Client-side staleness cue on status.html** (done 07-05).
- ✅ **PRODUCTION_READINESS honesty note** re retired-path controls (done 07-05).
- ▫ **Gate accumulate/forward heartbeats on error-fraction** — a total yfinance
  outage records "healthy" with 0 bars. ~2 lines/file. (Careful: weekend
  nothing-to-fetch is legitimately 0 — gate on errors, not on 0-appended.)
- ▫ **Retry + heartbeat-on-failure in the trade path** — extract the dashboard's
  3x backoff into a shared helper for `account_snapshot()`; one transient KIS 500
  currently skips the day's rebalance. ~15 lines. (Value LOW-MED: band-based slow
  rebalance tolerates a missed day.)
- ▫ **Re-source live exposure signal** from the tracked index (`^GSPC`/`^KS200`)
  or the traded ETF's own series, not the 704-name EW basket. MEDIUM — **must
  re-run the R11 grid on the new series first** (live params were tuned on baskets).
- ▫ **GO_LIVE_RUNBOOK**: disambiguate the two `reconcile` functions (the runbook's
  "position-drift pre-flight" actually reconciles forward-return IC on the retired
  fusion journal).

## P2 — worth doing, not urgent

- ▫ Post-close beta reconcile (record ACTUAL filled qty vs the intent/ack-only
  ledger) reusing `reconcile.py`/`filled_orders()`; log-only, drift flag.
- ▫ Repoint/remove the weekly `run_reconcile` cron (fires Sat for the retired strategy).
- ▫ Price orders from KIS venue marks (already fetched); demote yfinance to a
  log-only cross-check; also fixes an uncaught yfinance-flake crash before the ledger write.
- ▫ Cross-source price-sanity abort (broker vs computed >20%).
- ▫ Research realism (none change the conclusion): time-varying rf in `beta_game`;
  model turnover cost & report gross+net (consistency with R9's KOSDAQ costing);
  sweep EWMA lambda on R11; report realized COMBINED book vol & label "15%" as
  per-sleeve. (Do NOT remove `vol_floor` — it's a div-by-zero guard, not dead code.)
- ▫ Extract shared KIS bootstrap out of the retired `run_daily.py` (money-path
  currently top-level-imports the dead FusionEngine stack).
- ▫ De-dupe equity math between `run_performance` and `status_dashboard`; persist
  last benchmark returns so the vs-b&h card isn't blank most of the day.
- ▫ Route the dashboard health rollup into `run_healthcheck`'s pager (NOT the
  20-min run_status — would over-alert).
- ▫ Equity-history sparkline (once the track accrues rows).

## P2/P3 explicitly REJECTED (record the verdict)

- ❌ Drawdown-based auto-de-risking — redundant with vol+trend, pro-cyclical.
- ❌ Route live path through full DailyActEngine/ResilientSubmitter now — LARGE,
  and a real-money go-live gate, not a paper task. Defer.

## P3 — marginal

- ▫ Weekday-aware staleness window (skip Sat/Sun; no holiday calendar).
- ▫ Delete `run_momentum.py` CLI only (keep the warned library fn — ew_backtest
  imports its `_compute_metrics`).
- ▫ Move `beta_kis_track.buggy-sizing.jsonl.bak` to an archive dir; drop the
  orphan `beta_kis_paper` heartbeat key (NOT `daily_run`).

## Bottom line
Solid and essentially feature-complete; **not "done"** — the live path is
monitored/tested thinner than the live path itself, and that's the honest P1
cluster. Ceiling unchanged: a defensive-beta paper tracker with **no tradable
alpha**; this backlog makes it more trustworthy, not more profitable.
