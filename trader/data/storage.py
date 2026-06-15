# trader/data/storage.py
from __future__ import annotations
import pyarrow as pa, pyarrow.parquet as pq
from datetime import datetime, timezone
from trader.core.events import BarEvent, Symbol, Market

def save_bars(bars: list[BarEvent], path: str) -> None:
    cols = {k: [] for k in ("ticker","market","currency","ts","open","high","low","close","volume","timeframe")}
    for b in bars:
        cols["ticker"].append(b.symbol.ticker); cols["market"].append(b.symbol.market.value)
        cols["currency"].append(b.symbol.currency); cols["ts"].append(b.ts.isoformat())
        cols["open"].append(b.open); cols["high"].append(b.high); cols["low"].append(b.low)
        cols["close"].append(b.close); cols["volume"].append(b.volume); cols["timeframe"].append(b.timeframe)
    pq.write_table(pa.table(cols), path)

def load_bars(path: str) -> list[BarEvent]:
    t = pq.read_table(path).to_pylist()
    out = []
    for r in t:
        sym = Symbol(r["ticker"], Market(r["market"]), r["currency"])
        ts = datetime.fromisoformat(r["ts"])
        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        out.append(BarEvent(sym, ts, r["open"], r["high"], r["low"], r["close"], r["volume"], r["timeframe"]))
    return out
