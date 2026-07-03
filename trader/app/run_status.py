# trader/app/run_status.py
"""One-command unified status for the makemoney paper system.

Consolidates account, performance, job health, data freshness and recent fills
into a single clean screen — no more tailing scattered logs — and writes
status.html for browsing.  Read-only.

Usage:
    python -m trader.app.run_status            # print + write status.html
    python -m trader.app.run_status --no-html  # print only
    python -m trader.app.run_status --quiet     # write status.html only
"""
from __future__ import annotations

import argparse

from trader.app.status_dashboard import gather_status, render_terminal, write_html


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="unified makemoney status dashboard")
    p.add_argument("--no-html", action="store_true", help="don't write status.html")
    p.add_argument("--quiet", action="store_true", help="write html only, no stdout")
    p.add_argument("--no-benchmarks", action="store_true",
                   help="skip yfinance benchmark fetch (faster/offline)")
    args = p.parse_args(argv)

    status = gather_status(with_benchmarks=not args.no_benchmarks)
    if not args.quiet:
        print(render_terminal(status))
    if not args.no_html:
        path = write_html(status)
        if not args.quiet:
            print(f"\n  → status.html written ({path}) — open in a browser")
    return 0 if status["healthy"] else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
