# trader/core/clock.py
from __future__ import annotations
from datetime import datetime
from typing import Protocol

class Clock(Protocol):
    def now(self) -> datetime: ...

class BacktestClock:
    def __init__(self): self._t: datetime | None = None
    def set(self, t: datetime) -> None: self._t = t
    def now(self) -> datetime:
        if self._t is None: raise RuntimeError("clock not set")
        return self._t
