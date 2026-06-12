"""Large liquid US equity universe for broad scanning (~900 names).
Full S&P 500 plus liquid mid/large-caps. Curated to avoid delisted tickers.
Kept in its own module so trading.py stays readable.
"""

# Full S&P 500 (as of 2025-2026) + high-liquidity additions.
SP500_FULL = [
    "A","AAPL","ABBV","ABNB","ABT","ACGL","ACN","ADBE","ADI","ADM","ADP","ADSK","AEE","AEP","AES","AFL","AIG","AIZ","AJG","AKAM","ALB","ALGN","ALL","ALLE","AMAT","AMCR","AMD","AME","AMGN","AMP","AMT","AMZN","ANET","ANSS","AON","AOS","APA","APD","APH","APTV","ARE","ATO","AVB","AVGO","AVY","AWK","AXON","AXP","AZO","BA","BAC","BALL","BAX","BBY","BDX","BEN","BF-B","BG","BIIB","BK","BKNG","BKR","BLDR","BLK","BMY","BR","BRO","BSX","BWA","BX","BXP",
    "C","CAG","CAH","CARR","CAT","CB","CBOE","CBRE","CCI","CCL","CDNS","CDW","CE","CEG","CF","CFG","CHD","CHRW","CHTR","CI","CINF","CL","CLX","CMA","CMCSA","CME","CMG","CMI","CMS","CNC","CNP","COF","COIN","COO","COP","COR","COST","CPAY","CPB","CPRT","CPT","CRL","CRM","CRWD","CSCO","CSGP","CSX","CTAS","CTLT","CTRA","CTSH","CTVA","CVS","CVX","CZR",
    "D","DAL","DAY","DD","DE","DECK","DELL","DFS","DG","DGX","DHI","DHR","DIS","DLR","DLTR","DOC","DOV","DOW","DPZ","DRI","DTE","DUK","DVA","DVN","DXCM",
    "EA","EBAY","ECL","ED","EFX","EG","EIX","EL","ELV","EMN","EMR","ENPH","EOG","EPAM","EQIX","EQR","EQT","ERIE","ES","ESS","ETN","ETR","EVRG","EW","EXC","EXPD","EXPE","EXR",
    "F","FANG","FAST","FCX","FDS","FDX","FE","FFIV","FI","FICO","FIS","FITB","FMC","FOX","FOXA","FRT","FSLR","FTNT","FTV",
    "GD","GDDY","GE","GEHC","GEN","GEV","GILD","GIS","GL","GLW","GM","GNRC","GOOG","GOOGL","GPC","GPN","GRMN","GS","GWW",
    "HAL","HAS","HBAN","HCA","HD","HES","HIG","HII","HLT","HOLX","HON","HPE","HPQ","HRL","HSIC","HST","HSY","HUBB","HUM","HWM",
    "IBM","ICE","IDXX","IEX","IFF","INCY","INTC","INTU","INVH","IP","IPG","IQV","IR","IRM","ISRG","IT","ITW","IVZ",
    "J","JBHT","JBL","JCI","JKHY","JNJ","JNPR","JPM",
    "K","KDP","KEY","KEYS","KHC","KIM","KKR","KLAC","KMB","KMI","KMX","KO","KR","KVUE",
    "L","LDOS","LEN","LH","LHX","LII","LIN","LKQ","LLY","LMT","LNT","LOW","LRCX","LULU","LUV","LVS","LW","LYB","LYV",
    "MA","MAA","MAR","MAS","MCD","MCHP","MCK","MCO","MDLZ","MDT","MET","META","MGM","MHK","MKC","MKTX","MLM","MMC","MMM","MNST","MO","MOH","MOS","MPC","MPWR","MRK","MRNA","MS","MSCI","MSFT","MSI","MTB","MTCH","MTD","MU",
    "NCLH","NDAQ","NDSN","NEE","NEM","NFLX","NI","NKE","NOC","NOW","NRG","NSC","NTAP","NTRS","NUE","NVDA","NVR","NWS","NWSA","NXPI",
    "O","ODFL","OKE","OMC","ON","ORCL","ORLY","OTIS","OXY",
    "PANW","PARA","PAYC","PAYX","PCAR","PCG","PEG","PEP","PFE","PFG","PG","PGR","PH","PHM","PKG","PLD","PLTR","PM","PNC","PNR","PNW","PODD","POOL","PPG","PPL","PRU","PSA","PSX","PTC","PWR","PYPL",
    "QCOM","QRVO",
    "RCL","REG","REGN","RF","RJF","RL","RMD","ROK","ROL","ROP","ROST","RSG","RTX","RVTY",
    "SBAC","SBUX","SCHW","SHW","SJM","SLB","SMCI","SNA","SNPS","SO","SOLV","SPG","SPGI","SRE","STE","STLD","STT","STX","STZ","SWK","SWKS","SYF","SYK","SYY",
    "T","TAP","TDG","TDY","TECH","TEL","TER","TFC","TGT","TJX","TMO","TMUS","TPR","TRGP","TRMB","TROW","TRV","TSCO","TSLA","TSN","TT","TTWO","TXN","TXT","TYL",
    "UAL","UBER","UDR","UHS","ULTA","UNH","UNP","UPS","URI","USB",
    "V","VICI","VLO","VLTO","VMC","VRSK","VRSN","VRTX","VST","VTR","VTRS","VZ",
    "WAB","WAT","WBA","WBD","WDC","WEC","WELL","WFC","WM","WMB","WMT","WRB","WST","WTW","WY","WYNN",
    "XEL","XOM","XYL","YUM","ZBH","ZBRA","ZTS",
]

# Liquid extras beyond the S&P 500 (growth, fintech, semis, miners, popular names).
EXTRAS = [
    "ABCL","AFRM","ALAB","APP","APLD","ARM","ASML","ASTS","AU","BABA","BIDU","BILI",
    "CART","CAVA","CELH","CHWY","CIFR","CLSK","COHR","COMP","CORZ","CRDO","CRSP","CVNA","DDOG","DKNG","DOCU",
    "DUOL","ELF","ENVX","ESTC","ETSY","FOUR","FUTU","GRAB","GTLB","HIMS","HOOD","HUT","IONQ","IOT","IREN",
    "JD","JOBY","KVYO","LCID","LI","LMND","LUNR","MARA","MDB","MELI","MNDY","MQ","MSTR","NBIS","NET","NIO",
    "NKLA","NNE","NTLA","NTNX","NU","OKLO","OKTA","ONON","OSCR","PATH","PINS","PLUG","PSTG","QBTS","QS",
    "RBLX","RBRK","RDDT","RGTI","RIOT","RIVN","RKLB","ROOT","RXRX","S","SE","SHOP","SMR","SNAP","SNOW","SOFI",
    "SOUN","SPOT","SQ","TEM","TOST","TTD","TWLO","U","UPST","VERX","VRT","WULF","ZETA","ZS","ZM",
    # More liquid mid/large-caps and popular movers
    "AA","AAL","ACAD","ACHC","ACI","ADT","AFG","AGCO","AGNC","AKAM","ALGM","ALKS","ALLY","ALSN","AMBA","AMC","AMKR","AN","ANF","APG","APLS","APO","AR","ARES","ARW","ARWR","ASAN","ASH","ASO","AVAV","AVTR","AXSM","AYI","AZEK","AZTA",
    "BAH","BC","BCO","BDC","BECN","BFAM","BHF","BIO","BJ","BKU","BLD","BLKB","BMRN","BOKF","BPMC","BRBR","BRKR","BRX","BSY","BURL","BWXT","BYD","BZH",
    "CABO","CACC","CACI","CADE","CAR","CASY","CBSH","CCK","CFR","CGNX","CHE","CHRD","CHX","CIEN","CLF","CLH","CMC","CNM","CNX","COKE","COLB","COLM","COOP","CPRI","CR","CRC","CRI","CROX","CRUS","CSL","CVLT","CW","CXT","CYTK",
    "DAR","DBX","DECK","DFH","DINO","DJT","DKS","DLB","DNB","DOCS","DOCU","DTM","DXC",
    "EAT","EBC","EEFT","EHC","ELAN","ELF","EME","ENS","ENSG","ENTG","EPAM","EQH","ESI","ETSY","EWBC","EXAS","EXEL","EXLS","EXP",
    "FAF","FBIN","FCFS","FCN","FELE","FFIN","FHB","FHN","FIVE","FIVN","FIX","FLEX","FLR","FLS","FN","FND","FNF","FOUR","FRPT","FSS","FTDR","FTRE","FYBR",
    "G","GAP","GATX","GBCI","GFS","GGG","GH","GKOS","GLOB","GME","GMED","GNTX","GPK","GTLS","GXO",
    "H","HALO","HAS","HBI","HCC","HGV","HLI","HLNE","HOG","HOMB","HQY","HRB","HUBS","HXL",
    "IART","IBKR","ICUI","IDA","IGT","ILMN","INFA","INGR","INSP","IPAR","IRDM","ITCI","ITT",
    "JAZZ","JEF","JHG","JLL","JWN","JXN",
    "KBR","KD","KEX","KFY","KGS","KNF","KNSL","KNX","KRC","KRG","KRYS",
    "LAD","LAMR","LANC","LAZ","LBRDK","LECO","LEG","LFUS","LITE","LNC","LNW","LOPE","LPLA","LSCC","LSTR","LYFT",
    "M","MAN","MANH","MAT","MC","MDGL","MEDP","MGY","MHO","MIDD","MKSI","MLI","MMS","MOD","MORN","MP","MRCY","MSA","MSGS","MTG","MTH","MTSI","MUR","MUSA",
    "NBIX","NCNO","NEU","NFG","NJR","NOG","NOV","NSA","NSP","NTRA","NVST","NVT","NWE","NXST","NYT",
    "OGE","OHI","OLED","OLN","OLLI","OMCL","ONB","ONTO","ORA","ORI","OSK","OVV","OZK",
    "PAG","PB","PBF","PCTY","PCVX","PEGA","PEN","PFGC","PII","PINC","PJT","PLNT","PNFP","POST","POWI","PR","PRGO","PRI","PRIM","PSN","PVH",
    "QGEN","QLYS","R","RBA","RBC","RDN","RGA","RGEN","RH","RHI","RIG","RL","RMBS","RNR","ROAD","ROIV","RPM","RRC","RRX","RYAN","RYN",
    "SAIA","SAIC","SAM","SARO","SATS","SCI","SEIC","SF","SFM","SGRY","SHC","SIG","SITM","SKX","SLGN","SLM","SM","SMG","SN","SNDR","SNV","SNX","SON","SPB","SPSC","SPXC","SSB","SSD","STAG","STEP","STNE","STRL","STWD","SUM","SWX","SXT","SYNA",
    "TALO","TBBK","TCBI","TDC","TDOC","TENB","TFII","TFX","TGTX","THC","THG","THO","TKO","TKR","TMHC","TNL","TOL","TPH","TPX","TREX","TRNO","TRU","TTC","TTEK","TTMI","TXNM","TXRH",
    "UAA","UFPI","UGI","UHAL","ULS","UMBF","UNF","UNM","UPWK","URBN","USFD","UWMC",
    "VC","VCYT","VFC","VKTX","VLY","VMI","VNO","VNOM","VNT","VOYA","VVV",
    "WAL","WCC","WEN","WEX","WFRD","WH","WHR","WING","WK","WMS","WSC","WSM","WSO","WTRG","WTS","WU","WWD","WYNN",
    "X","XHR","XPO","XRAY","YETI","YOU","ZION","ZWS","ZYME",
]

def large_universe() -> list:
    """~900 unique liquid US tickers for broad scanning."""
    seen = {}
    for t in SP500_FULL + EXTRAS:
        t = t.strip()
        if t and t not in seen:
            seen[t] = True
    return list(seen.keys())


_LISTING_CACHE = {"ts": 0, "tickers": None}

def all_exchange_tickers(include_nasdaq: bool = True) -> list:
    """Fetch the FULL current NYSE (+ optionally NASDAQ) common-stock listing
    from a maintained public source. Cached 24h. Falls back to large_universe()
    if the network is unavailable.

    The raw listing has thousands of symbols incl. illiquid names; the scanner's
    batch fetch + price/liquidity filters drop the junk so only real tradeable
    stocks reach scoring.
    """
    import time as _t
    now = _t.time()
    if _LISTING_CACHE["tickers"] is not None and (now - _LISTING_CACHE["ts"]) < 86400:
        return _LISTING_CACHE["tickers"]
    import urllib.request
    base = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main"
    urls = [f"{base}/nyse/nyse_tickers.txt"]
    if include_nasdaq:
        urls.append(f"{base}/nasdaq/nasdaq_tickers.txt")
    collected = {}
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=15).read().decode()
            for line in data.splitlines():
                t = line.strip().upper()
                # Common stock only: skip warrants/units/preferred/rights and blanks.
                if not t or len(t) > 5:
                    continue
                if any(c in t for c in (".", "^", "$", "/", " ")):
                    continue
                collected[t] = True
        except Exception:
            continue
    if collected:
        tickers = list(collected.keys())
        _LISTING_CACHE["tickers"] = tickers
        _LISTING_CACHE["ts"] = now
        return tickers
    return large_universe()
