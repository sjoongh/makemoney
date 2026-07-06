# Monitoring setup — makemoney

The dead-man switch and alerting are wired but need two URLs pasted into `.env`
to actually reach you. Without them the system can silently stop (Mac asleep,
cron unfired) and you'd only find out by opening `status.html` yourself.

## 1. Push alerts (in-band) — `ALERT_WEBHOOK_URL`

Sends a CRITICAL message when a monitored job is stale. Any incoming-webhook
works (Slack / Discord / Telegram bridge). Only CRITICAL fires (no spam).

```
# .env
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

Limitation: this is **in-band** — if the Mac is asleep/off, this webhook can't
fire either. That's what #2 solves.

## 2. External dead-man ping — `HEALTHCHECK_PING_URL`  ← the important one

Catches the #1 failure mode (host down), which no in-band monitor can. Use a
free "expect-a-ping" service:

1. Create a free check at **https://healthchecks.io** (or cronitor.io).
2. Set its **period = 12h** and **grace = 2h** (healthcheck cron runs 09:00 &
   18:00 KST → a ping is expected twice a day; if none arrives, IT emails/texts
   you).
3. Paste the check's ping URL:

```
# .env
HEALTHCHECK_PING_URL=https://hc-ping.com/your-uuid-here
```

How it behaves (`run_healthcheck.py`):
- all jobs fresh  → GET `<url>`        (proves the host + all jobs are alive)
- something stale → GET `<url>/fail`   (raises the alert immediately)
- Mac asleep/off  → no ping at all     → healthchecks.io alerts you after the grace window

That last line is the whole point: **only an external service can tell you the
computer itself went dark.**

## Verify
```
HEALTHCHECK_PING_URL=https://hc-ping.com/your-uuid ./.venv/bin/python -m trader.app.run_healthcheck
```
Then confirm the check flipped to "up" on the healthchecks.io dashboard.

## Also hardened (no config needed)
- `accumulate_data` / `run_forward_record` no longer record a "healthy"
  heartbeat on a **total fetch outage** (every symbol errored) — so a full
  yfinance/network failure now actually trips the switch instead of looking green.
- `status.html` shows a red "갱신 멈춤?" cue if the writer cron dies during the
  KST 09–23 write window.
