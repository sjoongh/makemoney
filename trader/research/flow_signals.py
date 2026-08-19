# trader/research/flow_signals.py
"""RESEARCH ONLY — adapt investor flows into SignalFns for the IC harness.

Free-data expansion R7. Score at rebalance date t is the turnover-normalized
flow imbalance: Σ net(field) / Σ volume over rows dated within
[t - window_days, t - embargo_days]. Flow rows are published after close →
embargo 1 day (usable from the next trading day), same point-in-time rule
as event signals.

Missing coverage returns None (unknown flows are NOT zero flows — the symbol
drops out of that date's cross-section instead of polluting it).

field="smart" scores 기관+외국인 combined net flow.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from trader.core.events import BarEvent
from trader.research.signal_eval import SignalFn


def _ticker(bar: BarEvent) -> str:
    sym = bar.symbol
    return getattr(sym, "ticker", None) or str(sym)


def make_flow_imbalance_signal(
    flows: list[dict],
    *,
    field: str,
    window_days: int,
    embargo_days: int = 1,
) -> SignalFn:
    """SignalFn: Σ net / Σ volume over [t - window_days, t - embargo_days]."""
    by_symbol: dict[str, list[tuple[date, float, float]]] = {}
    for r in flows:
        net = (
            float(r["inst_net"]) + float(r["frgn_net"])
            if field == "smart"
            else float(r[field])
        )
        by_symbol.setdefault(r["symbol"], []).append(
            (date.fromisoformat(r["date"]), net, float(r["volume"]))
        )
    for rows in by_symbol.values():
        rows.sort()

    def signal(bars: list[BarEvent]) -> Optional[float]:
        if not bars:
            return None
        t = bars[-1].ts.date()
        rows = by_symbol.get(_ticker(bars[-1]))
        if not rows:
            return None
        lo = t - timedelta(days=window_days)
        hi = t - timedelta(days=embargo_days)
        net = vol = 0.0
        for d, n, v in rows:
            if lo <= d <= hi:
                net += n
                vol += v
        if vol <= 0:
            return None
        return net / vol

    return signal
