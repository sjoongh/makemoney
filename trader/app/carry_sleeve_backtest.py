import glob, os, json, numpy as np
from datetime import date, timedelta
from trader.data.storage import load_bars

fund=json.load(open('crypto_data/_funding.json'))
panel={}
for p in sorted(glob.glob('crypto_data/CRYPTO_*.parquet')):
    c=os.path.basename(p)[7:-8]
    if c in fund:
        b=load_bars(p)
        if b: panel[c]=b
fd={c:{date.fromisoformat(k):v for k,v in fund[c].items()} for c in panel}
alld=sorted({d for c in fd for d in fd[c]})
print(f"coins {len(panel)}, funding span {alld[0]} → {alld[-1]}")

TAKER=0.001   # 0.1% per leg
def trail(c,d,w=7):
    vals=[fd[c][d-timedelta(days=k)] for k in range(w) if (d-timedelta(days=k)) in fd[c]]
    return sum(vals)/len(vals) if len(vals)>=max(3,w//2) else None

def backtest(d0,d1,rebal=7):
    idx=[d for d in alld if d0<=d.isoformat()<=d1] if isinstance(d0,str) else [d for d in alld if d0<=d<=d1]
    held=set(); daily=[]
    for i,d in enumerate(idx):
        # rebalance every `rebal` days: pick positive-trailing-funding coins
        if i%rebal==0:
            new={c for c in panel if (trail(c,d) or 0)>0 and d in fd[c]}
            turnover=len(new.symmetric_difference(held))/max(1,len(new|held))
            cost=TAKER*2*turnover      # both legs on changed positions
            held=new
        else:
            cost=0.0
        if held:
            # today's realized funding collected (delta-neutral short-perp receives positive funding)
            fs=[fd[c][d] for c in held if d in fd[c]]
            r=(np.mean(fs) if fs else 0.0) - cost
        else:
            r=-cost
        daily.append(r)
    a=np.array(daily)
    if len(a)<5: return None
    eq=np.cumprod(1+a); peak=np.maximum.accumulate(eq); dd=((eq-peak)/peak).min()
    cagr=eq[-1]**(365/len(a))-1
    sh=a.mean()/a.std()*np.sqrt(365) if a.std()>0 else 0
    return dict(cagr=cagr, sharpe=sh, maxdd=dd, ndays=len(a), final=eq[-1])

print("\n=== 캐리 슬리브 백테스트 (주간 리밸, 0.1%/leg 비용, 실제 펀딩 P&L) ===")
for lbl,s,e in [('TRAIN(20-22)','2020-09-01','2022-06-30'),('VAL(22-24)','2022-07-01','2024-12-31'),('HOLDOUT(25-26)','2025-01-01',alld[-1].isoformat())]:
    r=backtest(s,e)
    if r: print(f"{lbl:<14} 슬리브 CAGR {r['cagr']:+6.1%}  Sharpe {r['sharpe']:5.2f}  MaxDD {r['maxdd']:6.1%}  ({r['ndays']}d)")

# full-period + total-capital + tail scenario
full=backtest(alld[0], alld[-1])
print(f"\n=== 전체기간 슬리브: CAGR {full['cagr']:+.1%}, Sharpe {full['sharpe']:.2f}, MaxDD {full['maxdd']:.1%} ===")
for alloc in (0.10,0.15,0.20):
    contrib=full['cagr']*alloc
    tail=-1.0*alloc   # 거래소 파산 = 슬리브 전액 손실
    yrs_to_recover=abs(tail)/max(contrib,1e-6)
    print(f"  배분 {alloc:.0%}: 총자본 기여 +{contrib:.1%}/yr | 거래소파산시 총자본 {tail:.0%} (회복에 ~{yrs_to_recover:.1f}년치 캐리)")
