# tests/test_risk.py
from trader.core.events import Symbol, Market, TargetPosition
from trader.strategy.risk import RiskManager

SYM = Symbol("AAPL", Market.NASDAQ, "USD")

def test_clamps_to_max_weight_and_no_short():
    rm = RiskManager(max_symbol_weight=0.3)
    assert rm.size_target(TargetPosition(SYM, 0.9)).target_weight == 0.3   # 클램프
    assert rm.size_target(TargetPosition(SYM, -0.5)).target_weight == 0.0  # 롱/현금만

def test_kill_switch_forces_flat():
    rm = RiskManager(max_symbol_weight=0.3); rm.trip_kill_switch()
    assert rm.size_target(TargetPosition(SYM, 0.9)).target_weight == 0.0
