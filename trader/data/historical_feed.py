# trader/data/historical_feed.py
from __future__ import annotations
from typing import Iterator
from trader.core.events import BarEvent

class InMemoryDailyFeed:
    """메모리 일봉 소스. 타임스탬프 오름차순으로 1개씩 yield.
    (parquet 로딩은 storage.py가 담당, 여기 주입)"""
    def __init__(self, bars: list[BarEvent]):
        self._bars = sorted(bars, key=lambda b: (b.ts, b.symbol.ticker))
    def events(self) -> Iterator[BarEvent]:
        yield from self._bars
