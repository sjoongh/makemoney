from __future__ import annotations

def total_return(equity_curve: list[float]) -> float:
    if len(equity_curve) < 2 or equity_curve[0] == 0: return 0.0
    return equity_curve[-1] / equity_curve[0] - 1.0

def max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]; mdd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak: mdd = min(mdd, (v - peak) / peak)
    return mdd
