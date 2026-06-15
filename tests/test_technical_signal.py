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


def test_two_symbols_do_not_pollute_each_others_window():
    from datetime import datetime, timezone, timedelta
    from trader.core.events import Symbol, Market, BarEvent
    from trader.signals.technical import TechnicalSignalSource
    a = Symbol("AAPL", Market.NASDAQ, "USD"); k = Symbol("005930", Market.KOSPI, "KRW")
    src = TechnicalSignalSource(2, 4)
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    # Interleave: A rising 1..6, K falling 6..1, alternating days
    a_close = [1,2,3,4,5,6]; k_close = [6,5,4,3,2,1]
    sig_a = sig_k = None
    for i in range(6):
        sig_a = src.on_bar(BarEvent(a, t0+timedelta(days=i*2),   a_close[i],a_close[i],a_close[i],a_close[i],100)) or sig_a
        sig_k = src.on_bar(BarEvent(k, t0+timedelta(days=i*2+1), k_close[i],k_close[i],k_close[i],k_close[i],100)) or sig_k
    # If windows were shared, signals would be garbage/equal. Per-symbol → A bullish, K bearish.
    assert sig_a is not None and sig_k is not None
    assert sig_a.score > 0 and sig_k.score < 0
