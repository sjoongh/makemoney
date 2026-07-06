import os
from datetime import datetime, timezone
from trader.core.events import BarEvent, Market, Symbol
from trader.data.storage import save_bars
from trader.data.quality import validate_bars
from trader.data.research_provider import _yf_download_normalize

OUT="crypto_data"; os.makedirs(OUT, exist_ok=True)
# Survivorship-aware curated union of coins that were prominent 2017-2026,
# INCLUDING ones that died (LUNA, UST, FTT) — excludes stablecoins & wrapped/staked.
UNIV = [
 "BTC","ETH","BNB","XRP","ADA","DOGE","SOL","DOT","LTC","TRX",
 "AVAX","LINK","XLM","XMR","ETC","XTZ","ATOM","ALGO","VET","FIL",
 "EOS","AAVE","MKR","NEO","DASH","ZEC","QTUM","WAVES","ICX","OMG",
 "ZRX","BAT","LSK","BTG","THETA","MANA","SAND","AXS","UNI","SUSHI",
 "COMP","SNX","CRV","YFI","GRT","ENJ","CHZ","LUNA","UST","FTT",
]
ok=err=0
for i,c in enumerate(UNIV):
    sym_str=f"{c}-USD"
    path=os.path.join(OUT, f"CRYPTO_{c}.parquet")
    if os.path.exists(path): ok+=1; continue
    try:
        rows=_yf_download_normalize(sym_str, years=12, auto_adjust=False)
    except Exception as e:
        print(f"  {c}: ERR {str(e)[:60]}", flush=True); err+=1; continue
    if not rows or len(rows)<252: print(f"  {c}: too short ({len(rows) if rows else 0})",flush=True); err+=1; continue
    sym=Symbol(c, Market.NASDAQ, "USD")
    bars=[BarEvent(sym, r["ts"], r["open"], r["high"], r["low"], r["close"], int(r.get("volume",0) or 0)) for r in rows if r["close"]>0]
    if len(bars)<252: err+=1; continue
    rep=validate_bars(bars)
    if not rep.passed: print(f"  {c}: quality fail",flush=True); err+=1; continue
    save_bars(bars,path); ok+=1
    if (i+1)%10==0: print(f"  {i+1}/{len(UNIV)} ok={ok} err={err}",flush=True)
print(f"DONE ok={ok} err={err} → {OUT}/",flush=True)
