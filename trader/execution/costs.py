from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class BpsCostModel:
    """명목가 * bps. 시장별 세금 nuance는 후속 보강(stub)."""
    bps: float = 0.0
    def commission(self, price: float, quantity: int) -> float:
        return price * quantity * (self.bps / 10_000.0)
