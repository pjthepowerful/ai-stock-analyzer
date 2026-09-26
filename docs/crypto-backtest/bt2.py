from bt import *
from bt import _roll
import numpy as np
def donch2(bars,ke,kx,L,X):
    n=L*12; nx=X*12
    HI=_roll([b[2] for b in bars],n,np.max); LO=_roll([b[3] for b in bars],nx,np.min)
    out=defaultdict(float); pos=0; prev=None; ntr=0
    for i in range(n,len(bars)):
        b=bars[i]; dk=day(b[0]); m=mod(b[0]+300)
        if pos and prev is not None: out[dk]+=b[4]/prev-1
        prev=b[4]
        if pos and m%kx==0 and b[4]<LO[i]: out[dk]-=COST; pos=0
        elif not pos and m%ke==0 and b[4]>HI[i]: out[dk]-=COST; pos=1; ntr+=1
        if not pos: prev=None
    return dict(out), ntr
data=load(); all_days=sorted({day(b[0]) for b in data["BTCUSD"]}); mid=all_days[len(all_days)//2]
def split(p): return stats({d:v for d,v in p.items() if d<mid}), stats({d:v for d,v in p.items() if d>=mid})
for ke,kx in ((60,60),(60,5),(60,15),(5,60)):
    for L,X in ((72,24),(48,24)):
        res={s:donch2(b,ke,kx,L,X) for s,b in data.items()}
        print(f"L{L} X{X} entry{ke} exit{kx} trades/token {sum(r[1] for r in res.values())/len(res):.0f}", *split(portfolio({s:r[0] for s,r in res.items()})), flush=True)
