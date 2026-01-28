"""
Paula - Stock Analysis Assistant
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from groq import Groq
from dotenv import load_dotenv
import os
import json
import re
import warnings

warnings.filterwarnings('ignore')
load_dotenv()

# Stock Lists
NASDAQ_100 = ['AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AVGO', 'COST', 'NFLX',
    'AMD', 'ADBE', 'PEP', 'CSCO', 'TMUS', 'INTC', 'CMCSA', 'INTU', 'QCOM', 'TXN',
    'AMGN', 'HON', 'AMAT', 'ISRG', 'BKNG', 'SBUX', 'VRTX', 'LRCX', 'MU', 'ADI',
    'MDLZ', 'REGN', 'ADP', 'PANW', 'KLAC', 'SNPS', 'CDNS', 'MELI', 'CRWD', 'ASML',
    'PYPL', 'MAR', 'ORLY', 'CTAS', 'MRVL', 'ABNB', 'NXPI', 'PCAR', 'WDAY', 'CPRT']

SP500_TOP = ['AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'BRK-B', 'LLY', 'TSLA', 'UNH',
    'JPM', 'XOM', 'V', 'JNJ', 'PG', 'MA', 'AVGO', 'HD', 'MRK', 'CVX',
    'COST', 'ABBV', 'PEP', 'KO', 'WMT', 'ADBE', 'MCD', 'CSCO', 'CRM', 'BAC']

NIFTY_50 = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'HINDUNILVR.NS',
    'BHARTIARTL.NS', 'SBIN.NS', 'BAJFINANCE.NS', 'ITC.NS', 'KOTAKBANK.NS', 'LT.NS',
    'HCLTECH.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'SUNPHARMA.NS', 'TITAN.NS',
    'WIPRO.NS', 'NTPC.NS', 'TATAMOTORS.NS', 'TATASTEEL.NS', 'ADANIENT.NS']

TRENDING = ['PLTR', 'SMCI', 'ARM', 'IONQ', 'RGTI', 'MSTR', 'COIN', 'HOOD', 'SOFI', 'RKLB',
    'RIVN', 'LCID', 'NIO', 'GME', 'AMC', 'DKNG', 'SNOW', 'NET', 'OKTA']

COMPANIES = {
    'apple': 'AAPL', 'microsoft': 'MSFT', 'amazon': 'AMZN', 'google': 'GOOGL',
    'meta': 'META', 'facebook': 'META', 'tesla': 'TSLA', 'nvidia': 'NVDA', 'netflix': 'NFLX',
    'amd': 'AMD', 'intel': 'INTC', 'adobe': 'ADBE', 'salesforce': 'CRM', 'oracle': 'ORCL',
    'paypal': 'PYPL', 'shopify': 'SHOP', 'spotify': 'SPOT', 'uber': 'UBER',
    'airbnb': 'ABNB', 'disney': 'DIS', 'nike': 'NKE', 'starbucks': 'SBUX', 
    'mcdonalds': 'MCD', 'walmart': 'WMT', 'costco': 'COST', 'boeing': 'BA',
    'coca cola': 'KO', 'pepsi': 'PEP', 'pfizer': 'PFE', 'moderna': 'MRNA', 
    'palantir': 'PLTR', 'crowdstrike': 'CRWD', 'snowflake': 'SNOW',
    'coinbase': 'COIN', 'robinhood': 'HOOD', 'sofi': 'SOFI', 'gamestop': 'GME',
    'reliance': 'RELIANCE', 'tcs': 'TCS', 'infosys': 'INFY', 'hdfc': 'HDFCBANK',
    'wipro': 'WIPRO', 'tata motors': 'TATAMOTORS', 'sbi': 'SBIN', 'itc': 'ITC'
}


def get_stock_price(ticker):
    """Get current stock price with multiple fallbacks"""
    try:
        stock = yf.Ticker(ticker)
        
        # Method 1: info dict
        try:
            info = stock.info
            if info:
                price = info.get('currentPrice') or info.get('regularMarketPrice')
                prev = info.get('previousClose') or info.get('regularMarketPreviousClose')
                if price and price > 0:
                    prev = prev or price
                    return {
                        'price': round(price, 2),
                        'prev_close': round(prev, 2),
                        'change': round(price - prev, 2),
                        'change_pct': round((price - prev) / prev * 100, 2) if prev > 0 else 0,
                        'name': info.get('shortName') or ticker,
                        'market_cap': info.get('marketCap'),
                        'pe_ratio': info.get('trailingPE'),
                        'forward_pe': info.get('forwardPE'),
                        '52w_high': info.get('fiftyTwoWeekHigh'),
                        '52w_low': info.get('fiftyTwoWeekLow'),
                        'sector': info.get('sector'),
                        'target_price': info.get('targetMeanPrice'),
                        'recommendation': info.get('recommendationKey'),
                    }
        except:
            pass
        
        # Method 2: history
        try:
            hist = stock.history(period='5d')
            if hist is not None and not hist.empty:
                price = float(hist['Close'].iloc[-1])
                prev = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else price
                if price > 0:
                    info = {}
                    try:
                        info = stock.info or {}
                    except:
                        pass
                    return {
                        'price': round(price, 2),
                        'prev_close': round(prev, 2),
                        'change': round(price - prev, 2),
                        'change_pct': round((price - prev) / prev * 100, 2) if prev > 0 else 0,
                        'name': info.get('shortName') or ticker,
                        'market_cap': info.get('marketCap'),
                        'pe_ratio': info.get('trailingPE'),
                        'forward_pe': info.get('forwardPE'),
                        '52w_high': info.get('fiftyTwoWeekHigh'),
                        '52w_low': info.get('fiftyTwoWeekLow'),
                        'sector': info.get('sector'),
                        'target_price': info.get('targetMeanPrice'),
                        'recommendation': info.get('recommendationKey'),
                    }
        except:
            pass
        
        return None
    except:
        return None


def get_full_data(ticker):
    """Get comprehensive stock data"""
    basic = get_stock_price(ticker)
    if not basic:
        return None
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        hist = stock.history(period='3mo')
        
        tech = {}
        if hist is not None and not hist.empty and len(hist) >= 20:
            c = hist['Close']
            tech['sma_20'] = round(c.rolling(20).mean().iloc[-1], 2)
            if len(c) >= 50:
                tech['sma_50'] = round(c.rolling(50).mean().iloc[-1], 2)
            
            delta = c.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            tech['rsi'] = round(100 - (100 / (1 + rs.iloc[-1])), 1)
            
            if len(c) >= 5:
                tech['mom_5d'] = round((c.iloc[-1] / c.iloc[-5] - 1) * 100, 2)
            if len(c) >= 20:
                tech['mom_20d'] = round((c.iloc[-1] / c.iloc[-20] - 1) * 100, 2)
        
        news = []
        try:
            for n in (stock.news or [])[:3]:
                news.append({'title': n.get('title', ''), 'publisher': n.get('publisher', '')})
        except:
            pass
        
        return {
            **basic,
            'ticker': ticker.replace('.NS', ''),
            'peg_ratio': info.get('pegRatio'),
            'roe': info.get('returnOnEquity'),
            'profit_margin': info.get('profitMargins'),
            'debt_to_equity': info.get('debtToEquity'),
            'dividend_yield': info.get('dividendYield'),
            'beta': info.get('beta'),
            'target_high': info.get('targetHighPrice'),
            'target_low': info.get('targetLowPrice'),
            'num_analysts': info.get('numberOfAnalystOpinions'),
            'industry': info.get('industry', 'N/A'),
            'technicals': tech,
            'news': news
        }
    except:
        return basic


def calc_score(data):
    """Calculate trading score"""
    score = 50
    signals, warns = [], []
    tech = data.get('technicals', {})
    price = data.get('price', 0)
    
    rsi = tech.get('rsi')
    if rsi:
        if rsi < 30:
            score += 15
            signals.append("RSI oversold")
        elif rsi > 70:
            score -= 15
            warns.append("RSI overbought")
    
    sma20 = tech.get('sma_20')
    if sma20 and price > sma20:
        score += 5
        signals.append("Above 20 SMA")
    elif sma20 and price < sma20:
        score -= 5
    
    mom = tech.get('mom_5d')
    if mom:
        if mom > 5:
            score += 8
            signals.append(f"5d momentum +{mom:.1f}%")
        elif mom < -5:
            score -= 8
            warns.append(f"5d momentum {mom:.1f}%")
    
    rec = data.get('recommendation')
    if rec in ['strongBuy', 'strong_buy']:
        score += 10
        signals.append("Strong Buy rating")
    elif rec == 'buy':
        score += 5
    elif rec in ['sell', 'strongSell']:
        score -= 10
        warns.append(f"Analyst: {rec}")
    
    target = data.get('target_price')
    if target and price:
        upside = (target - price) / price * 100
        if upside > 15:
            score += 5
            signals.append(f"{upside:.0f}% upside to target")
        elif upside < -10:
            warns.append(f"{abs(upside):.0f}% below target")
    
    score = max(0, min(100, score))
    
    if score >= 70:
        rating = "🟢 STRONG BUY"
    elif score >= 55:
        rating = "🟢 BUY"
    elif score >= 40:
        rating = "🟡 HOLD"
    elif score >= 25:
        rating = "🟠 CAUTION"
    else:
        rating = "🔴 AVOID"
    
    return {'score': score, 'rating': rating, 'signals': signals, 'warnings': warns}


def make_chart(ticker, period='3mo'):
    """Create price chart"""
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist is None or hist.empty:
            return None
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'],
            low=hist['Low'], close=hist['Close'], name='Price',
            increasing_line_color='#22c55e', decreasing_line_color='#ef4444'), row=1, col=1)
        
        if len(hist) >= 20:
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'].rolling(20).mean(),
                name='SMA20', line=dict(color='#3b82f6', width=1)), row=1, col=1)
        
        colors = ['#22c55e' if c >= o else '#ef4444' for c, o in zip(hist['Close'], hist['Open'])]
        fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], marker_color=colors, opacity=0.5), row=2, col=1)
        
        fig.update_layout(template='plotly_dark', paper_bgcolor='#09090b', plot_bgcolor='#09090b',
            font=dict(color='#a1a1aa'), showlegend=False, height=350,
            margin=dict(l=0, r=0, t=20, b=0), xaxis_rangeslider_visible=False)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor='#27272a')
        
        return fig
    except:
        return None


def find_ticker(msg):
    """Find ticker in message"""
    m = msg.lower()
    for name, tick in COMPANIES.items():
        if name in m:
            return tick
    
    exclude = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'BUY', 'SELL',
               'WHAT', 'WHICH', 'STOCK', 'PRICE', 'MARKET', 'TODAY', 'SHOULD', 'WOULD', 'COULD',
               'ABOUT', 'THEIR', 'WILL', 'WITH', 'THIS', 'THAT', 'FROM', 'HAVE', 'BEEN', 'MORE',
               'ANALYZE', 'TELL', 'SHOW', 'GIVE', 'FIND', 'BEST', 'GOOD', 'HIGH', 'LOW', 'MONEY'}
    
    all_stocks = set(NASDAQ_100 + SP500_TOP + [s.replace('.NS', '') for s in NIFTY_50] + TRENDING)
    
    for word in msg.upper().split():
        clean = re.sub(r'[^A-Z]', '', word)
        if clean and 2 <= len(clean) <= 5 and clean not in exclude and clean in all_stocks:
            return clean
    return None


def detect_intent(msg):
    """Detect user intent"""
    m = msg.lower()
    
    if any(m.strip() == g for g in ['hi', 'hello', 'hey', 'thanks', 'help']):
        return {'type': 'chat'}
    
    if any(w in m for w in ['price of', "what's", 'what is', 'how much']):
        t = find_ticker(msg)
        if t:
            return {'type': 'price', 'ticker': t}
    
    if any(w in m for w in ['analyze', 'analysis', 'should i buy', 'verdict']):
        t = find_ticker(msg)
        if t:
            return {'type': 'analyze', 'ticker': t}
    
    if any(w in m for w in ['gainer', 'best stock', 'top performer']):
        return {'type': 'gainers'}
    if any(w in m for w in ['loser', 'worst', 'dropping']):
        return {'type': 'losers'}
    if any(w in m for w in ['hot', 'trending', 'moving', 'recommend']):
        return {'type': 'hot'}
    
    t = find_ticker(msg)
    if t:
        return {'type': 'analyze', 'ticker': t}
    
    return {'type': 'chat'}


def run_intent(intent, market='US'):
    """Execute intent"""
    t = intent.get('type')
    
    if t == 'price':
        ticker = intent['ticker']
        if market == 'India' and '.' not in ticker:
            ticker = f"{ticker}.NS"
        data = get_stock_price(ticker)
        if data:
            sym = '$' if market == 'US' else '₹'
            clr = '🟢' if data['change_pct'] >= 0 else '🔴'
            return {
                'ok': True, 'type': 'price',
                'msg': f"**{ticker.replace('.NS', '')}** {sym}{data['price']:,.2f} ({clr} {data['change_pct']:+.2f}%)",
                'data': data
            }
        return {'ok': False, 'error': f"Could not fetch {ticker}"}
    
    if t == 'analyze':
        ticker = intent['ticker']
        if market == 'India' and '.' not in ticker:
            ticker = f"{ticker}.NS"
        data = get_full_data(ticker)
        if data:
            sc = calc_score(data)
            return {'ok': True, 'type': 'analysis', 'data': {**data, **sc}, 'ticker': ticker}
        return {'ok': False, 'error': f"Could not fetch {ticker}"}
    
    if t == 'gainers':
        stocks = NIFTY_50 if market == 'India' else NASDAQ_100
        results = []
        for s in stocks[:30]:
            d = get_stock_price(s)
            if d and d['change_pct'] > 0:
                results.append({'ticker': s.replace('.NS', ''), 'price': d['price'], 'change_pct': d['change_pct']})
        results.sort(key=lambda x: x['change_pct'], reverse=True)
        return {'ok': True, 'type': 'list', 'title': 'Top Gainers', 'data': results[:10]}
    
    if t == 'losers':
        stocks = NIFTY_50 if market == 'India' else NASDAQ_100
        results = []
        for s in stocks[:30]:
            d = get_stock_price(s)
            if d and d['change_pct'] < 0:
                results.append({'ticker': s.replace('.NS', ''), 'price': d['price'], 'change_pct': d['change_pct']})
        results.sort(key=lambda x: x['change_pct'])
        return {'ok': True, 'type': 'list', 'title': 'Top Losers', 'data': results[:10]}
    
    if t == 'hot':
        results = []
        for s in (TRENDING + NASDAQ_100[:15])[:30]:
            d = get_stock_price(s)
            if d:
                results.append({'ticker': s, 'price': d['price'], 'change_pct': d['change_pct']})
        results.sort(key=lambda x: abs(x['change_pct']), reverse=True)
        return {'ok': True, 'type': 'list', 'title': 'Hot Stocks', 'data': results[:10]}
    
    return {'ok': False, 'type': 'chat'}


def get_ai(msg, data, history, market='US'):
    """Get AI response"""
    key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not key:
        return "Add GROQ_API_KEY to secrets."
    
    try:
        client = Groq(api_key=key)
        
        sys = f"""You are Paula, a stock assistant. Be concise and natural.
Date: {datetime.now().strftime("%Y-%m-%d")} | Market: {market}
- Use the data provided, don't say you can't access prices
- Short answers for simple questions
- Never start with "I"
- No excessive bullet points"""

        msgs = [{"role": "system", "content": sys}]
        for h in history[-4:]:
            msgs.append({"role": h["role"], "content": h["content"]})
        
        content = f"{msg}\n\nData:\n{json.dumps(data, default=str)}" if data else msg
        msgs.append({"role": "user", "content": content})
        
        resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs, max_tokens=800, temperature=0.7)
        return resp.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)[:80]}"


def main():
    st.set_page_config(page_title="Paula", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
    
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
    * { font-family: 'DM Sans', sans-serif; }
    .stApp { background: #09090b; }
    header, footer, #MainMenu { visibility: hidden; }
    .block-container { max-width: 850px; padding: 2rem 1rem; }
    h1, h2, h3 { color: #fafafa !important; }
    p, span, div, label { color: #a1a1aa !important; }
    .stChatMessage { background: #18181b !important; border: 1px solid #27272a !important; border-radius: 12px !important; }
    .stChatMessage p, .stChatMessage span { color: #e4e4e7 !important; }
    .stTextInput > div > div > input { background: #18181b !important; border: 1px solid #27272a !important; color: #fafafa !important; }
    .stButton > button { background: #18181b !important; color: #fafafa !important; border: 1px solid #27272a !important; }
    .stButton > button:hover { background: #27272a !important; }
    .stSelectbox > div > div { background: #18181b !important; border: 1px solid #27272a !important; }
    .stExpander { background: #18181b !important; border: 1px solid #27272a !important; }
    hr { border-color: #27272a !important; }
    </style>
    """, unsafe_allow_html=True)
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'market' not in st.session_state:
        st.session_state.market = 'US'
    if 'show_charts' not in st.session_state:
        st.session_state.show_charts = True
    
    col1, col2 = st.columns([3, 1])
    with col1:
        icon = "🇺🇸" if st.session_state.market == 'US' else "🇮🇳"
        st.markdown(f"## Paula {icon}")
        st.caption("Stock analysis")
    with col2:
        with st.expander("⚙️"):
            st.session_state.market = st.selectbox("Market", ['US', 'India'], index=0 if st.session_state.market == 'US' else 1)
            st.session_state.show_charts = st.checkbox("Charts", value=st.session_state.show_charts)
            if st.button("Clear"):
                st.session_state.messages = []
                st.rerun()
    
    st.markdown("---")
    
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["role"] == "assistant" and m.get("chart") and st.session_state.show_charts:
                ch = make_chart(m["chart"])
                if ch:
                    st.plotly_chart(ch, use_container_width=True)
            if m["role"] == "assistant" and m.get("table"):
                st.dataframe(pd.DataFrame(m["table"]), use_container_width=True, hide_index=True)
    
    if prompt := st.chat_input("Ask about any stock..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner(""):
                ml = prompt.lower()
                if any(w in ml for w in ['nifty', 'sensex', 'reliance', 'india']):
                    st.session_state.market = 'India'
                elif any(w in ml for w in ['nasdaq', 's&p', 'apple', 'tesla']):
                    st.session_state.market = 'US'
                
                mkt = st.session_state.market
                intent = detect_intent(prompt)
                res = run_intent(intent, mkt)
                
                chart_t = None
                table_d = None
                
                if res.get('ok'):
                    if res['type'] == 'price':
                        resp = res['msg']
                    elif res['type'] == 'analysis':
                        chart_t = res['ticker']
                        resp = get_ai(prompt, res['data'], st.session_state.messages, mkt)
                    elif res['type'] == 'list':
                        table_d = res['data']
                        sym = '₹' if mkt == 'India' else '$'
                        for i in table_d:
                            clr = '🟢' if i['change_pct'] >= 0 else '🔴'
                            i['Change'] = f"{clr} {i['change_pct']:+.2f}%"
                            i['Price'] = f"{sym}{i['price']:,.2f}"
                            del i['change_pct'], i['price']
                        resp = f"**{res['title']}**"
                    else:
                        resp = get_ai(prompt, None, st.session_state.messages, mkt)
                elif res.get('error'):
                    resp = f"⚠️ {res['error']}"
                else:
                    resp = get_ai(prompt, None, st.session_state.messages, mkt)
                
                st.markdown(resp)
                if chart_t and st.session_state.show_charts:
                    ch = make_chart(chart_t)
                    if ch:
                        st.plotly_chart(ch, use_container_width=True)
                if table_d:
                    st.dataframe(pd.DataFrame(table_d), use_container_width=True, hide_index=True)
        
        st.session_state.messages.append({"role": "assistant", "content": resp, "chart": chart_t, "table": table_d})
    
    st.markdown("---")
    st.caption("Not financial advice.")


if __name__ == "__main__":
    main()
