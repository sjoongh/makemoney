# trader/signals/technical.py
from __future__ import annotations
from collections import deque
import numpy as np
from trader.core.events import BarEvent, NormalizedSignal

def _rsi(closes: list[float], n: int = 14) -> float:
    if len(closes) < n + 1: return 50.0
    d = np.diff(closes[-(n+1):])
    up = d[d > 0].sum() / n; dn = -d[d < 0].sum() / n
    if dn == 0: return 100.0
    rs = up / dn
    return 100.0 - 100.0 / (1.0 + rs)

def _ema(vals: list[float], n: int) -> float:
    k = 2.0 / (n + 1); e = vals[0]
    for v in vals[1:]: e = v * k + e * (1 - k)
    return e

class TechnicalSignalSource:
    """롤링/증분, 닫힌 봉만. MA 교차 + RSI + MACD + Bollinger 합성."""
    name = "technical"
    def __init__(self, fast: int = 20, slow: int = 50):
        self.fast, self.slow = fast, slow
        self._windows: dict[tuple[str, str], deque[float]] = {}
    def on_bar(self, bar: BarEvent) -> NormalizedSignal | None:
        key = (bar.symbol.market.value, bar.symbol.ticker)
        if key not in self._windows:
            self._windows[key] = deque(maxlen=max(self.slow, 60))
        self._windows[key].append(bar.close)
        if len(self._windows[key]) < self.slow: return None
        c = list(self._windows[key])
        ma_fast = sum(c[-self.fast:]) / self.fast
        ma_slow = sum(c[-self.slow:]) / self.slow
        ma_score = max(-1.0, min(1.0, ((ma_fast - ma_slow) / ma_slow if ma_slow else 0.0) * 10))
        rsi = _rsi(c); rsi_score = max(-1.0, min(1.0, (rsi - 50.0) / 50.0))
        macd_hist = _ema(c, 12) - _ema(c, 26)
        macd_score = max(-1.0, min(1.0, macd_hist / (ma_slow or 1.0) * 10))
        window = c[-self.fast:]; mean = sum(window)/len(window)
        std = (sum((x-mean)**2 for x in window)/len(window)) ** 0.5
        bb_pos = (bar.close - mean) / (2*std) if std else 0.0
        bb_score = max(-1.0, min(1.0, bb_pos))
        score = float(np.clip(np.mean([ma_score, rsi_score, macd_score, bb_score]), -1.0, 1.0))
        return NormalizedSignal("technical", bar.symbol, bar.ts, score=score, confidence=0.6,
                                horizon="1d",
                                features={"ma_fast":ma_fast,"ma_slow":ma_slow,"rsi":rsi,
                                          "macd_hist":macd_hist,"bb_pos":bb_pos})
