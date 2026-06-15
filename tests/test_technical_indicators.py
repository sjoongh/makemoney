# tests/test_technical_indicators.py
from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.signals.technical import TechnicalSignalSource

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def test_features_include_rsi_macd_bollinger():
    src = TechnicalSignalSource(3,6)
    t0 = datetime(2026,1,1,tzinfo=timezone.utc); sig=None
    for i,c in enumerate([1,2,1,3,2,4,3,5,4,6,5,7]):
        sig = src.on_bar(BarEvent(SYM, t0+timedelta(days=i), c,c,c,c,100)) or sig
    assert sig is not None
    for k in ("rsi","macd_hist","bb_pos"): assert k in sig.features
