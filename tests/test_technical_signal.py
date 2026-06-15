# tests/test_technical_signal.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.signals.technical import TechnicalSignalSource

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

def test_warmup_returns_none_until_enough_bars():
    src = TechnicalSignalSource(fast=2, slow=4)
    bars = _bars([1,2,3])
    sigs = [src.on_bar(b) for b in bars]
    assert sigs[-1] is None  # slow window 미충족

def test_uptrend_yields_positive_score():
    src = TechnicalSignalSource(fast=2, slow=4)
    sig = None
    for b in _bars([1,2,3,4,5,6]): sig = src.on_bar(b) or sig
    assert sig is not None and sig.score > 0 and sig.source == "technical"
