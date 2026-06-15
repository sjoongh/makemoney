# trader/data/recorder.py
from __future__ import annotations
from trader.core.events import BarEvent

class BarRecorder:
    """라이브 세션 봉 스트림 녹화 → 후일 백테스트로 재생(비트단위 패리티 검증)."""
    def __init__(self): self.bars: list[BarEvent] = []
    def record_bar(self, bar: BarEvent) -> None: self.bars.append(bar)
