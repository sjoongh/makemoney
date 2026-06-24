# trader/app/run_forward_record.py
"""RESEARCH ONLY — daily forward data recorder CLI (run after close via cron).

Records reality as it prints, going forward, to build a SURVIVORSHIP-BIAS-FREE
point-in-time dataset (see trader/data/forward_recorder.py):
  - appends today's universe membership to research_data/_universe_log.jsonl
  - appends finalized RAW (unadjusted) daily bars to forward_data/

NEVER import from live/paper trading or the backtest/live parity path.

Usage (cron, after the US/KR close):
    python -m trader.app.run_forward_record
    python -m trader.app.run_forward_record --us-limit 503 --kr-limit 200
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from trader.data.forward_recorder import record_forward
from trader.data.universe import universe


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="[RESEARCH ONLY] daily forward data recorder (point-in-time, raw)"
    )
    p.add_argument("--us-limit", type=int, default=503)
    p.add_argument("--kr-limit", type=int, default=200)
    p.add_argument("--no-kr", action="store_true")
    args = p.parse_args(argv)

    now = datetime.now(tz=timezone.utc)
    today = now.date()
    as_of = today.isoformat()

    print("=" * 60)
    print(f"[RESEARCH ONLY] Forward recorder — as_of {as_of}")
    print("  Records point-in-time RAW bars + universe membership going forward.")
    print("  Survivorship-free by construction; value compounds over time.")
    print("=" * 60)

    uni = universe(us_limit=args.us_limit, kr=not args.no_kr, kr_limit=args.kr_limit)
    print(f"  Universe: {len(uni)} symbols")

    summary = record_forward(as_of, today, uni)

    print("\n" + "-" * 40)
    print("Forward record summary:")
    print(f"  Membership logged: {summary['membership_logged']}")
    print(f"  Symbols:           {summary['symbols']}")
    print(f"  Symbols updated:   {summary['symbols_updated']}")
    print(f"  Bars appended:     {summary['bars_appended']}")
    print(f"  Errors:            {summary['errors']}")


if __name__ == "__main__":
    main()
