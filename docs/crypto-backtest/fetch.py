import sys, os, json, time, requests
from datetime import datetime, timedelta, timezone
UNIV=["BTC/USD","ETH/USD","SOL/USD","XRP/USD","DOGE/USD","ADA/USD","AVAX/USD","LINK/USD","LTC/USD","BCH/USD","DOT/USD","UNI/USD","AAVE/USD","SHIB/USD","PEPE/USD","HYPE/USD","SUI/USD","ARB/USD","RENDER/USD","ONDO/USD","WIF/USD","BONK/USD","TRUMP/USD","CRV/USD","LDO/USD","FIL/USD","POL/USD","XTZ/USD","GRT/USD","SUSHI/USD","BAT/USD","YFI/USD","SKY/USD"]
end=datetime(2026,9,26,tzinfo=timezone.utc); start=end-timedelta(days=180)
for s in UNIV:
    fn=s.replace('/','')+'.json'
    if os.path.exists(fn): continue
    out=[];tok=None
    while True:
        p={"symbols":s,"timeframe":"5Min","start":start.isoformat().replace('+00:00','Z'),"end":end.isoformat().replace('+00:00','Z'),"limit":10000,"sort":"asc"}
        if tok:p["page_token"]=tok
        for a in range(5):
            try: r=requests.get("https://data.alpaca.markets/v1beta3/crypto/us/bars",params=p,timeout=30)
            except Exception: time.sleep(3); continue
            if r.status_code==429: time.sleep(5);continue
            break
        j=r.json()
        out+= [[int(datetime.fromisoformat(b["t"].replace("Z","+00:00")).timestamp()),b["o"],b["h"],b["l"],b["c"],b["v"]] for b in (j.get("bars") or {}).get(s,[])]
        tok=j.get("next_page_token")
        if not tok:break
    json.dump(out,open(fn,'w')); print(s,len(out),flush=True)
