# trader/signals/technical.py
from __future__ import annotations
from collections import deque
from trader.core.events import BarEvent, NormalizedSignal

class TechnicalSignalSource:
    """롤링/증분. 닫힌 봉만 누적 — 미래 데이터 접근 없음. Phase 1: 이동평균 교차."""
    name = "technical"
    def __init__(self, fast: int = 20, slow: int = 50):
        self.fast, self.slow = fast, slow
        self._closes: deque[float] = deque(maxlen=slow)
    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
        self._closes.append(bar.close)
        if len(self._closes) < self.slow:
            return None
        closes = list(self._closes)
        ma_fast = sum(closes[-self.fast:]) / self.fast
        ma_slow = sum(closes) / self.slow
        spread = (ma_fast - ma_slow) / ma_slow if ma_slow else 0.0
        score = max(-1.0, min(1.0, spread * 10.0))  # 정규화
        return NormalizedSignal("technical", bar.symbol, bar.ts,
                                score=score, confidence=0.6, horizon="1d",
                                features={"ma_fast": ma_fast, "ma_slow": ma_slow})
