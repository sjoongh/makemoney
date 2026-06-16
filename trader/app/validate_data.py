# trader/app/validate_data.py
"""CLI for data quality validation.

Usage
-----
Validate specific file(s):
    python -m trader.app.validate_data research_data/KOSPI_005930.parquet

Validate all parquet files in research_data/:
    python -m trader.app.validate_data --all

IMPORTANT: Run this BEFORE trusting any dataset in research.
A non-zero exit code means at least one dataset has FAIL-severity issues
and should NOT be used for backtesting or signal generation until fixed.
"""
from __future__ import annotations

import sys
from pathlib import Path

from trader.data.quality import validate_parquet


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print("Usage: python -m trader.app.validate_data [paths...] [--all]", file=sys.stderr)
        print("  --all   validate all *.parquet files under research_data/", file=sys.stderr)
        return 2

    paths: list[Path] = []

    if "--all" in args:
        # Find research_data/ relative to the project root (two levels up from this file)
        project_root = Path(__file__).parent.parent.parent
        research_dir = project_root / "research_data"
        if not research_dir.exists():
            print(f"ERROR: research_data/ not found at {research_dir}", file=sys.stderr)
            return 2
        paths = sorted(research_dir.glob("*.parquet"))
        if not paths:
            print(f"No parquet files found in {research_dir}", file=sys.stderr)
            return 2
        # Filter out non-KOSPI/stock manifest or metadata files by checking they load
    else:
        for arg in args:
            p = Path(arg)
            if not p.exists():
                print(f"ERROR: file not found: {arg}", file=sys.stderr)
                return 2
            paths.append(p)

    any_fail = False
    reports = []

    for path in paths:
        try:
            report = validate_parquet(str(path))
            reports.append(report)
            if not report.passed:
                any_fail = True
        except Exception as exc:
            print(f"ERROR loading {path}: {exc}", file=sys.stderr)
            any_fail = True
            continue

    print("=" * 70)
    print("DATA QUALITY VALIDATION REPORT")
    print("=" * 70)
    for report in reports:
        print(report.summary())
        print()

    print("=" * 70)
    if any_fail:
        print("OVERALL: FAIL — one or more datasets have FAIL-severity issues.")
        print("Do NOT use failing datasets in research until issues are resolved.")
    else:
        print("OVERALL: PASS — all datasets cleared quality checks.")
    print("=" * 70)

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
