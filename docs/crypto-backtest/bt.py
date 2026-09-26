import json, glob, math, statistics, sys
from datetime import datetime, timezone
from collections import defaultdict
COST = 0.003   # per side: 0.25% Alpaca taker fee + 0.05% slippage
SKIP = {"USDTUSD","USDCUSD","USDGUSD","PAXGUSD"}
def load():
    d={}
    for f in sorted(glob.glob("*.json")):
        s=f[:-5]
        if s in SKIP: continue
        b=json.load(open(f))
        if len(b) > 30000: d[s]=b
    return d
def day(ts): return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()
def mod(ts): d=datetime.fromtimestamp(ts,timezone.utc); return d.hour*60+d.minute

def noise(bars, k, lookback=14, flat=23*60+50):
    """UTC-day noise area, long only, VWAP trail, flat by 23:50. Returns {day: ret}."""
    days=defaultdict(list)
    for b in bars: days[day(b[0])].append(b)
    ds=sorted(days); out={}; hist=[]
    for i,dk in enumerate(ds):
        bs=days[dk]; o=bs[0][1]
        mv={}; last=0
        bym={mod(b[0]):abs(b[4]/o-1) for b in bs}
        if len(hist)>=lookback//2:
            sig={}
            for m in range(0,1440,5):
                v=[h.get(m,0) for h in hist[-lookback:]]; sig[m]=sum(v)/len(v)
            pos=0; entry=0; r=0.0; pv=vv=0
            for b in bs:
                pv+=b[4]*b[5]; vv+=b[5]; vw=pv/vv if vv else b[4]
                m=mod(b[0])+5  # bar closes
                if m>=flat:
                    if pos: r+=b[4]/entry-1-COST; pos=0
                    continue
                if m<30 or m%k: continue
                up=o*(1+sig.get(m-5,0))
                if pos and b[4]<max(up,vw): r+=b[4]/entry-1-COST; pos=0
                elif not pos and b[4]>up: pos=1; entry=b[4]*(1+0); r-=COST
            if pos: r+=bs[-1][4]/entry-1-COST
            out[dk]=r
        h={}; last=0
        for m in range(0,1440,5): last=bym.get(m,last); h[m]=last
        hist.append(h)
    return out

def _roll(a, n, fn):
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view
    w = fn(sliding_window_view(np.asarray(a), n), axis=1)   # w[j] covers a[j:j+n]
    out = np.full(len(a), np.nan); out[n:] = w[:len(a)-n]    # window ending before bar i
    return out

_cache = {}
def donchian(bars, k, L, X, sym=None):
    """24/7: buy when close > highest high of last L hours; sell when close < lowest low of last X hours."""
    import numpy as np
    n=L*12; nx=X*12
    key=(id(bars),n,nx)
    if key not in _cache:
        _cache[key]=(_roll([b[2] for b in bars], n, np.max), _roll([b[3] for b in bars], nx, np.min))
    HI, LO = _cache[key]
    out=defaultdict(float); pos=0; prev=None
    for i in range(n, len(bars)):
        b=bars[i]; dk=day(b[0])
        if pos and prev is not None: out[dk]+=b[4]/prev-1
        prev=b[4]
        if mod(b[0]+300)%k: continue
        if pos and b[4] < LO[i]: out[dk]-=COST; pos=0
        elif not pos and b[4] > HI[i]: out[dk]-=COST; pos=1
        if not pos: prev=None
    return dict(out)

def stats(daily):
    if not daily: return {}
    ds=sorted(daily); r=[daily[d] for d in ds]
    eq=1; peak=1; dd=0
    for x in r: eq*=1+x; peak=max(peak,eq); dd=min(dd,eq/peak-1)
    sd=statistics.pstdev(r) or 1e-9
    return {"ret%":round((eq-1)*100,1),"sharpe":round(statistics.mean(r)/sd*math.sqrt(365),2),"maxdd%":round(dd*100,1)}

def portfolio(per):
    days=sorted(set().union(*[set(v) for v in per.values()]))
    return {d: sum(v.get(d,0) for v in per.values())/len(per) for d in days}

if __name__=="__main__":
    data=load(); syms=list(data); print(len(syms),"tokens:",",".join(syms))
    all_days=sorted({day(b[0]) for b in data["BTCUSD"]}); mid=all_days[len(all_days)//2]
    def split(p): 
        a={d:v for d,v in p.items() if d<mid}; b={d:v for d,v in p.items() if d>=mid}
        return stats(a), stats(b)
    bh={s:{} for s in syms}
    for s,bs in data.items():
        cl={}
        for b in bs: cl[day(b[0])]=b[4]
        ks=sorted(cl); bh[s]={ks[i]:cl[ks[i]]/cl[ks[i-1]]-1 for i in range(1,len(ks))}
    print("split at",mid)
    print("buy&hold EW    ", *split(portfolio(bh)))
    for k in (5,15,30,60):
        print(f"noise k={k:<3}    ", *split(portfolio({s:noise(b,k) for s,b in data.items()})), flush=True)
    for L,X in ((12,6),(24,6),(24,12),(48,12),(48,24),(72,24)):
        for k in (5,15,60):
            print(f"donch L{L} X{X} k={k:<3}", *split(portfolio({s:donchian(b,k,L,X) for s,b in data.items()})), flush=True)
