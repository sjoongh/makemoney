# trader/data/kis_live_feed.py
from __future__ import annotations
from typing import Iterator
from trader.core.events import BarEvent

class KisLiveFeed:
    """KIS 일봉을 표준 BarEvent로. Phase 1은 '최신 닫힌 일봉' 폴링 모델.
    (실거래에서는 장 마감 후 1회/스케줄 폴링; 인트라데이/웹소켓은 후속)"""
    def __init__(self, kis_client, symbols: list[tuple[str, str, str]]):
        self._kis = kis_client; self._symbols = symbols

    def events(self) -> Iterator[BarEvent]:
        bars: list[BarEvent] = []
        for ticker, market, currency in self._symbols:
            bars.extend(self._kis.daily_bars(ticker, market, currency))
        for b in sorted(bars, key=lambda x: (x.ts, x.symbol.ticker)):
            yield b
