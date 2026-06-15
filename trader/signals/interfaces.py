# trader/signals/interfaces.py
from __future__ import annotations
from typing import Protocol
from trader.core.events import BarEvent, NormalizedSignal

class SignalSource(Protocol):
    name: str
    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
        """닫힌 봉 1개 → 정규화 신호 0/1개. 내부 롤링 상태만, 미래 데이터 접근 금지."""
        ...
