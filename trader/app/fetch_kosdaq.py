import os, FinanceDataReader as fdr
from datetime import datetime, timezone
from trader.core.events import BarEvent, Market, Symbol
from trader.data.storage import save_bars
from trader.data.quality import validate_bars

OUT="kosdaq_data"; os.makedirs(OUT, exist_ok=True)
lst=fdr.StockListing('KOSDAQ')
lst=lst[lst['Marcap'].notna()].copy()
# 소형주 버킷: 시총 순위 100~500 (대형 코스닥 제외, 극소 dust 제외) + 유동성(거래대금>1e9)
lst=lst.sort_values('Marcap', ascending=False).reset_index(drop=True)
bucket=lst.iloc[100:500]
if 'Amount' in bucket.columns:
    bucket=bucket[bucket['Amount']>1_000_000_000]
codes=list(bucket['Code'])[:250]
print(f"universe: {len(codes)} KOSDAQ small-caps (liquidity-filtered)", flush=True)
sym_ccy="KRW"; ok=skip=err=0
for i,code in enumerate(codes):
    path=os.path.join(OUT, f"KOSDAQ_{code}.parquet")
    if os.path.exists(path): skip+=1; continue
    try:
        df=fdr.DataReader(code,'2016')
    except Exception as e: err+=1; continue
    if df is None or len(df)<252: err+=1; continue
    sym=Symbol(code, Market.KOSPI, sym_ccy)
    bars=[]
    for idx,row in df.iterrows():
        ts=datetime(idx.year,idx.month,idx.day,tzinfo=timezone.utc)
        o,h,l,c,v=row['Open'],row['High'],row['Low'],row['Close'],row['Volume']
        if c<=0 or o<=0: continue
        bars.append(BarEvent(sym,ts,float(o),float(h),float(l),float(c),int(v)))
    if len(bars)<252: err+=1; continue
    rep=validate_bars(bars)
    if not rep.passed: err+=1; continue
    save_bars(bars,path); ok+=1
    if (i+1)%50==0: print(f"  {i+1}/{len(codes)} ok={ok} skip={skip} err={err}", flush=True)
print(f"DONE ok={ok} skip={skip} err={err} → {OUT}/", flush=True)
