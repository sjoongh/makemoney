from __future__ import annotations
from rich.console import Console
from trader.backtest.metrics import total_return, max_drawdown

def print_report(equity_curve: list[float], final_equity_krw: float) -> dict:
    stats = {"total_return": total_return(equity_curve),
             "max_drawdown": max_drawdown(equity_curve),
             "final_equity_krw": final_equity_krw}
    Console().print(stats)
    return stats
