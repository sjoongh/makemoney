# tests/test_metrics.py
from trader.backtest.metrics import total_return, max_drawdown

def test_total_return():
    assert round(total_return([100, 110]), 4) == 0.10
def test_max_drawdown():
    assert round(max_drawdown([100, 120, 90, 110]), 4) == round((90-120)/120, 4)
