# Operations Guide — Daily Paper-Trading Runner

## Overview

`trader/app/run_daily.py` is a once-per-trading-day runner for KIS paper trading.
`scripts/run_daily.sh` is the thin wrapper that routes stdout/stderr to a datestamped
log file and accepts a market argument for per-market scheduling.

---

## How to Run Manually

```bash
# Dry-run (safe — no orders submitted):
bash scripts/run_daily.sh KOSPI
bash scripts/run_daily.sh NASDAQ
bash scripts/run_daily.sh ALL

# Live (submits real paper orders — see WARNING below):
bash scripts/run_daily.sh KOSPI --live
bash scripts/run_daily.sh NASDAQ --live
```

Logs are written to `logs/run_daily_<MARKET>_<YYYYMMDD>.log`.

---

## Scheduling with cron

Each market runs at its own close time via `TZ=` per cron entry.
Add these lines to your crontab (`crontab -e`):

```cron
# KRX (KOSPI) — closes 15:30 KST; run at 15:40 KST Mon-Fri
TZ=Asia/Seoul
40 15 * * 1-5 /path/to/makemoney/scripts/run_daily.sh KOSPI --live >> /path/to/makemoney/logs/cron_kospi.log 2>&1

# US (NASDAQ) — closes 16:00 ET; run at 16:10 ET Mon-Fri
TZ=America/New_York
10 16 * * 1-5 /path/to/makemoney/scripts/run_daily.sh NASDAQ --live >> /path/to/makemoney/logs/cron_nasdaq.log 2>&1
```

Replace `/path/to/makemoney` with the absolute path to your repo.

---

## WARNING: --live places real (paper) orders unattended

**Do NOT enable `--live` until you have observed dry-run behaviour for several trading days.**

Recommended procedure:

1. Run WITHOUT `--live` for a few days (default dry-run).
2. Inspect `logs/run_daily_<MARKET>_<date>.log` after each run:
   - Confirm the correct symbols are selected.
   - Verify the FX rate and account snapshot look reasonable.
   - Confirm the staleness guard fires on weekends/holidays (no orders generated).
3. Once satisfied, add `--live` to the cron lines above.

---

## Safety mechanisms

### Idempotency ledger

`RunLedger` (`.run_ledger.json`) records every `(account, date, market, ticker)` tuple
that has been submitted. If the runner is invoked twice on the same day (e.g., cron
retry or manual re-run), the second invocation skips already-submitted tickers.
No double-submits.

### Staleness guard (data-driven, no calendar dependency)

`DailyActEngine` derives a reference date from the **maximum latest-bar date across
all fetched symbols** — no system clock involved. Any symbol whose latest bar is more
than `max_staleness_days` (default 4) days older than that reference is skipped for
action (warm-up only). This means:

- **Weekends**: the exchange prints no new bar — the staleness guard fires and no
  orders are generated. Safe to leave the cron running 7 days/week if desired.
- **Public holidays**: same logic — no fresh bar means no trade.
- **Exchange-specific closures**: if one market is closed but the other is open,
  the open market's bar is fresh (staleness=0) and the closed market's bar is stale
  and skipped automatically.

No external calendar or holiday library is needed.

---

## Inspecting state

```bash
# Tail the most recent KOSPI log:
tail -f logs/run_daily_KOSPI_$(date +%Y%m%d).log

# View the idempotency ledger:
cat .run_ledger.json | python -m json.tool

# Check what orders would be generated (dry-run, single market):
.venv/bin/python -m trader.app.run_daily --market KOSPI
```
