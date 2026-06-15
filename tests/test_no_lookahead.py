# tests/test_no_lookahead.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.signals.technical import TechnicalSignalSource

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100) for i,c in enumerate(closes)]

def test_signal_at_bar_t_unaffected_by_future_bars():
    """봉 t에서의 신호는 t 이후 봉을 추가로 줘도 동일해야 한다 (증분/롤링 보장)."""
    closes = [1,2,3,4,5,6,7,8,9,10]
    a = TechnicalSignalSource(3,6); b = TechnicalSignalSource(3,6)
    bars = _bars(closes)
    sig_a = None
    for bar in bars[:7]: sig_a = a.on_bar(bar) or sig_a
    sig_b = None
    for bar in bars: sig_b_t7 = b.on_bar(bar);  sig_b = sig_b_t7 if bar is bars[6] else sig_b
    # 7번째 봉까지 본 a의 마지막 신호 == 전체를 본 b가 7번째 봉에서 낸 신호
    assert sig_a is not None and sig_b is not None
    assert abs(sig_a.score - sig_b.score) < 1e-9
