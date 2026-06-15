from datetime import datetime, timezone, timedelta
from trader.core.events import Symbol, Market, BarEvent
from trader.data.historical_feed import InMemoryDailyFeed
from trader.data.recorder import BarRecorder
from trader.data.storage import save_bars, load_bars

SYM = Symbol("AAPL", Market.NASDAQ, "USD")
def _bars(closes):
    t0 = datetime(2026,1,1,tzinfo=timezone.utc)
    return [BarEvent(SYM, t0+timedelta(days=i), c,c+1,c-1,c+0.5,100) for i,c in enumerate(closes)]

def test_recorded_bars_roundtrip_identical(tmp_path):
    rec = BarRecorder()
    for b in _bars([1,2,3,4]): rec.record_bar(b)
    p = tmp_path / "rec.parquet"
    save_bars(rec.bars, str(p))
    loaded = load_bars(str(p))
    # 재적재한 봉으로 만든 feed가 원본과 동일한 시퀀스를 낸다
    assert [(b.symbol.ticker, b.ts, b.close) for b in InMemoryDailyFeed(loaded).events()] == \
           [(b.symbol.ticker, b.ts, b.close) for b in InMemoryDailyFeed(rec.bars).events()]
