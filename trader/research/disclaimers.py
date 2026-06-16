# trader/research/disclaimers.py
"""Canonical survivorship-bias and research-limitation disclaimers.

Import SURVIVORSHIP_WARNING wherever research output is formatted so that
every consumer sees the same honest caveat.
"""
from __future__ import annotations

SURVIVORSHIP_WARNING = """\
╔══════════════════════════════════════════════════════════════════════════════╗
║  ⚠️  SURVIVORSHIP-BIASED EXPLORATORY ONLY                                   ║
║                                                                              ║
║  Universe = CURRENT index constituents (S&P 500 / KOSPI large-caps).        ║
║  Delisted, merged, and historically-removed names are EXCLUDED.              ║
║  This inflates momentum, trend-following, and quality-factor results         ║
║  because only today's survivors are tested.                                  ║
║                                                                              ║
║  Results are NOT evidence of real trading edge.  Point-in-time index         ║
║  membership data is required before any credible forward-looking claim       ║
║  can be made.  Treat all outputs as exploratory diagnostics only.            ║
╚══════════════════════════════════════════════════════════════════════════════╝"""
