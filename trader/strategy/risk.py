# trader/strategy/risk.py
from __future__ import annotations
from trader.core.events import TargetPosition

class RiskManager:
    def __init__(self, max_symbol_weight: float = 0.3):
        self.max_symbol_weight = max_symbol_weight
        self._killed = False
    def trip_kill_switch(self) -> None: self._killed = True
    def size_target(self, target: TargetPosition) -> TargetPosition:
        w = target.target_weight
        if self._killed or w <= 0.0:
            w = 0.0
        else:
            w = min(w, self.max_symbol_weight)
        return TargetPosition(target.symbol, w, target.reason)
