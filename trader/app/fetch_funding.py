import requests, time, json
from datetime import datetime, timezone
HOST="https://fapi.binance.com"
COINS=["BTC","ETH","BNB","XRP","ADA","DOGE","SOL","DOT","LTC","TRX",
       "AVAX","LINK","XLM","ATOM","ALGO","FIL","AAVE","MKR","ETC","XTZ",
       "SAND","MANA","AXS","UNI","SUSHI","CRV","SNX","ENJ","CHZ","GRT"]
START=int(datetime(2019,1,1,tzinfo=timezone.utc).timestamp()*1000)
NOW=int(datetime(2026,7,7,tzinfo=timezone.utc).timestamp()*1000)
out={}
for c in COINS:
    sym=f"{c}USDT"; rows=[]; start=START; last=None
    while start<NOW:
        try:
            r=requests.get(HOST+"/fapi/v1/fundingRate",
                           params={"symbol":sym,"startTime":start,"limit":1000}, timeout=15)
            if r.status_code!=200: time.sleep(1.0); 
            data=r.json() if r.status_code==200 else []
        except Exception: break
        if not data: break
        rows.extend(data)
        newlast=max(d["fundingTime"] for d in data)
        if newlast==last: break
        last=newlast; start=newlast+1
        if len(data)<1000: break
        time.sleep(0.15)
    daily={}
    for d in rows:
        dt=datetime.fromtimestamp(d["fundingTime"]/1000, tz=timezone.utc).date().isoformat()
        daily[dt]=daily.get(dt,0.0)+float(d["fundingRate"])
    if daily: out[c]=daily
    ds=sorted(daily)
    print(f"  {c}: {len(rows)} pts, {len(daily)} days, {ds[0] if ds else '-'}→{ds[-1] if ds else '-'}",flush=True)
    time.sleep(0.15)
json.dump(out, open("crypto_data/_funding.json","w"))
print(f"DONE {len(out)} coins",flush=True)
