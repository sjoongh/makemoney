# trader/data/interfaces.py
from __future__ import annotations
from typing import Protocol, Iterator
from trader.core.events import BarEvent

class DataFeed(Protocol):
    def events(self) -> Iterator[BarEvent]:
        """시간순 증가하는 '닫힌' BarEvent를 1개씩 yield. 과거/라이브 동일 계약."""
        ...
