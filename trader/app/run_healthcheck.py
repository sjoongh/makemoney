# trader/app/run_healthcheck.py
"""Dead-man's switch — alert if a scheduled job stopped firing.

Reads the heartbeat file and alerts (via the live Monitor / WebhookAlertSink)
when any component is stale or never ran — catching the silent failure where
cron simply doesn't fire (laptop asleep / off). Run on its own cron a few times
a day. Exits non-zero if anything is stale.

Set ALERT_WEBHOOK_URL (Slack/Telegram/Discord incoming webhook) to get a push;
otherwise alerts go to the log only.

Observability only — never places orders.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from trader.live import heartbeat as hb
from trader.live.monitor import LogAlertSink, Monitor, WebhookAlertSink

# component -> max age in hours before it's considered stale.
# Daily data jobs run every day (weekends too); the trade dry-runs run on
# weekdays, so they get a weekend-tolerant window.
DEFAULT_EXPECTATIONS = {
    "accumulator": 30.0,       # cron daily (runs every day)
    "forward_record": 30.0,    # cron daily 14:00 (runs every day)
    # THE order-submitting jobs — weekday runs; weekend-tolerant window.
    # (fusion daily_run was removed 2026-07-01; audit found the dead-man switch
    #  monitored everything EXCEPT the jobs that actually place orders.)
    "beta_kis_kr": 80.0,
    "beta_kis_us": 80.0,
}


def _build_monitor() -> Monitor:
    # load .env so ALERT_WEBHOOK_URL set there is honoured under cron
    # (audit: healthcheck never called _load_dotenv → webhook silently unused)
    if "ALERT_WEBHOOK_URL" not in os.environ:
        try:
            from trader.app.run_daily import _load_dotenv
            _load_dotenv()
        except Exception:
            pass
    sinks = [LogAlertSink()]
    url = os.environ.get("ALERT_WEBHOOK_URL")
    if url:
        sinks.append(WebhookAlertSink(url))
    return Monitor(sinks)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="heartbeat dead-man's switch healthcheck")
    p.add_argument("--path", default=hb.DEFAULT_PATH)
    p.add_argument("--ignore-missing", action="store_true",
                   help="don't alert on components that have NEVER recorded "
                        "(useful right after install, before any run)")
    args = p.parse_args(argv)

    now = datetime.now(tz=timezone.utc)
    stale = hb.check(now, DEFAULT_EXPECTATIONS, path=args.path)
    if args.ignore_missing:
        stale = [s for s in stale if s["reason"] != "never recorded"]

    monitor = _build_monitor()
    if not stale:
        monitor.alert("INFO", "HEARTBEAT_OK",
                      {"checked": list(DEFAULT_EXPECTATIONS)})
        print("OK — all heartbeats fresh.")
        return 0

    for s in stale:
        monitor.alert("CRITICAL", "HEARTBEAT_STALE", s)
    print(f"STALE ({len(stale)}): " + ", ".join(s["component"] for s in stale))
    return 1


if __name__ == "__main__":
    sys.exit(main())
