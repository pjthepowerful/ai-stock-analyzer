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
    'wipro': 'WIPRO', 'tata motors': 'TATAMOTORS', 'sbi': 'SBIN', 'itc': 'ITC',
    'icici': 'ICICIBANK', 'kotak': 'KOTAKBANK', 'airtel': 'BHARTIARTL', 'bharti': 'BHARTIARTL'
}

# Indian market indicators for auto-detect
INDIA_KEYWORDS = ['nifty', 'sensex', 'bse', 'nse', 'india', 'indian', 'rupee', '₹',
    'reliance', 'tcs', 'infosys', 'hdfc', 'icici', 'sbi', 'wipro', 'tata', 'airtel',
    'bharti', 'kotak', 'axis', 'maruti', 'titan', 'itc', 'adani', 'bajaj', 'mahindra']

US_KEYWORDS = ['nasdaq', 's&p', 'sp500', 'dow', 'nyse', 'dollar', '$', 'us market',
    'apple', 'microsoft', 'google', 'amazon', 'meta', 'tesla', 'nvidia', 'amd',
    'netflix', 'disney', 'nike', 'starbucks', 'walmart', 'costco', 'boeing']


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
            
            sma20 = c.rolling(20).mean()
            std20 = c.rolling(20).std()
            tech['bb_upper'] = round((sma20 + 2 * std20).iloc[-1], 2)
            tech['bb_lower'] = round((sma20 - 2 * std20).iloc[-1], 2)
            
            if len(c) >= 5:
                tech['mom_5d'] = round((c.iloc[-1] / c.iloc[-5] - 1) * 100, 2)
            if len(c) >= 20:
                tech['mom_20d'] = round((c.iloc[-1] / c.iloc[-20] - 1) * 100, 2)
            
            if 'Volume' in hist.columns:
                avg_vol = hist['Volume'].rolling(20).mean().iloc[-1]
                today_vol = hist['Volume'].iloc[-1]
                tech['vol_ratio'] = round(today_vol / avg_vol, 2) if avg_vol > 0 else 1
        
        news = []
        try:
            for n in (stock.news or [])[:5]:
                news.append({'title': n.get('title', ''), 'publisher': n.get('publisher', '')})
        except:
            pass
        
        return {
            **basic,
            'ticker': ticker.replace('.NS', ''),
            'full_ticker': ticker,
            'peg_ratio': info.get('pegRatio'),
            'roe': info.get('returnOnEquity'),
            'profit_margin': info.get('profitMargins'),
            'revenue_growth': info.get('revenueGrowth'),
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
            signals.append(f"RSI oversold at {rsi:.0f} - potential bounce opportunity")
        elif rsi < 40:
            score += 8
            signals.append(f"RSI in buy zone at {rsi:.0f}")
        elif rsi > 70:
            score -= 15
            warns.append(f"RSI overbought at {rsi:.0f} - risk of pullback")
        elif rsi > 60:
            score -= 5
    
    sma20 = tech.get('sma_20')
    sma50 = tech.get('sma_50')
    if sma20 and price > sma20:
        score += 5
        signals.append(f"Trading above 20-day SMA (${sma20:.2f}) - short-term uptrend")
    elif sma20 and price < sma20:
        score -= 5
        warns.append(f"Below 20-day SMA (${sma20:.2f})")
    
    if sma50 and price > sma50:
        score += 5
        signals.append(f"Above 50-day SMA - medium-term uptrend intact")
    
    mom5 = tech.get('mom_5d')
    mom20 = tech.get('mom_20d')
    if mom5:
        if mom5 > 5:
            score += 8
            signals.append(f"Strong 5-day momentum: +{mom5:.1f}%")
        elif mom5 > 0:
            score += 3
        elif mom5 < -5:
            score -= 8
            warns.append(f"Weak 5-day momentum: {mom5:.1f}%")
    
    if mom20:
        if mom20 > 10:
            signals.append(f"20-day momentum: +{mom20:.1f}%")
        elif mom20 < -10:
            warns.append(f"20-day momentum: {mom20:.1f}%")
    
    vol = tech.get('vol_ratio')
    if vol:
        if vol > 1.5:
            score += 5
            signals.append(f"Volume {vol:.1f}x average - strong conviction")
        elif vol < 0.5:
            warns.append("Low volume - weak conviction")
    
    pe = data.get('pe_ratio')
    fwd_pe = data.get('forward_pe')
    if pe and fwd_pe:
        if fwd_pe < pe * 0.9:
            score += 5
            signals.append(f"Forward P/E ({fwd_pe:.1f}) < Trailing P/E ({pe:.1f}) - earnings growth expected")
    
    rec = data.get('recommendation')
    if rec:
        if rec in ['strongBuy', 'strong_buy']:
            score += 10
            signals.append("Wall Street consensus: Strong Buy")
        elif rec == 'buy':
            score += 5
            signals.append("Wall Street consensus: Buy")
        elif rec in ['sell', 'strongSell']:
            score -= 10
            warns.append(f"Wall Street consensus: {rec}")
    
    target = data.get('target_price')
    if target and price:
        upside = (target - price) / price * 100
        if upside > 20:
            score += 8
            signals.append(f"Analyst target ${target:.2f} implies {upside:.0f}% upside")
        elif upside > 10:
            score += 4
            signals.append(f"Analyst target ${target:.2f} ({upside:.0f}% upside)")
        elif upside < -10:
            score -= 5
            warns.append(f"Trading {abs(upside):.0f}% above analyst target")
    
    high_52 = data.get('52w_high')
    low_52 = data.get('52w_low')
    if high_52 and low_52 and price:
        range_pct = (price - low_52) / (high_52 - low_52) * 100 if (high_52 - low_52) > 0 else 50
        if range_pct < 20:
            score += 5
            signals.append(f"Near 52-week low - potential value play")
        elif range_pct > 90:
            warns.append(f"Near 52-week high - extended")
    
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
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist is None or hist.empty or len(hist) < 5:
            # Try shorter period
            hist = stock.history(period='1mo')
            if hist is None or hist.empty:
                return None
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        
        # Candlestick chart
        fig.add_trace(go.Candlestick(
            x=hist.index, 
            open=hist['Open'], 
            high=hist['High'],
            low=hist['Low'], 
            close=hist['Close'], 
            name='Price',
            increasing_line_color='#22c55e', 
            decreasing_line_color='#ef4444'
        ), row=1, col=1)
        
        # Moving averages
        if len(hist) >= 20:
            sma20 = hist['Close'].rolling(20).mean()
            fig.add_trace(go.Scatter(
                x=hist.index, y=sma20, name='SMA 20',
                line=dict(color='#3b82f6', width=1.5)
            ), row=1, col=1)
        
        if len(hist) >= 50:
            sma50 = hist['Close'].rolling(50).mean()
            fig.add_trace(go.Scatter(
                x=hist.index, y=sma50, name='SMA 50',
                line=dict(color='#f59e0b', width=1.5)
            ), row=1, col=1)
        
        # Volume bars
        colors = ['#22c55e' if c >= o else '#ef4444' for c, o in zip(hist['Close'], hist['Open'])]
        fig.add_trace(go.Bar(
            x=hist.index, y=hist['Volume'], 
            marker_color=colors, opacity=0.5, name='Volume'
        ), row=2, col=1)
        
        # Layout
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor='#0a0a0a',
            plot_bgcolor='#0a0a0a',
            font=dict(color='#a1a1aa', size=12),
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            height=450,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis_rangeslider_visible=False
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor='#1f1f1f')
        
        return fig
    except Exception as e:
        # Return None silently - chart just won't show
        return None


def auto_detect_market(msg):
    """Auto-detect which market based on message content"""
    m = msg.lower()
    
    india_score = sum(1 for k in INDIA_KEYWORDS if k in m)
    us_score = sum(1 for k in US_KEYWORDS if k in m)
    
    if india_score > us_score:
        return 'India'
    elif us_score > india_score:
        return 'US'
    return None  # No clear signal


def find_ticker(msg, market='US'):
    """Find ticker in message"""
    m = msg.lower()
    
    # Check company names first
    for name, tick in COMPANIES.items():
        if name in m:
            # Check if it's an Indian company
            if tick in ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'WIPRO', 'SBIN', 'ITC', 'KOTAKBANK', 'BHARTIARTL', 'TATAMOTORS']:
                return tick, 'India'
            return tick, 'US'
    
    exclude = {'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'BUY', 'SELL',
               'WHAT', 'WHICH', 'STOCK', 'PRICE', 'MARKET', 'TODAY', 'SHOULD', 'WOULD', 'COULD',
               'ABOUT', 'THEIR', 'WILL', 'WITH', 'THIS', 'THAT', 'FROM', 'HAVE', 'BEEN', 'MORE',
               'ANALYZE', 'TELL', 'SHOW', 'GIVE', 'FIND', 'BEST', 'GOOD', 'HIGH', 'LOW', 'MONEY',
               'WHEN', 'WHERE', 'SOME', 'INTO', 'TIME', 'VERY', 'JUST', 'KNOW', 'TAKE', 'COME',
               'MAKE', 'LIKE', 'BACK', 'ONLY', 'OVER', 'SUCH', 'MOST', 'NEED', 'HELP', 'THANK'}
    
    us_stocks = set(NASDAQ_100 + SP500_TOP + TRENDING)
    india_stocks = set(s.replace('.NS', '') for s in NIFTY_50)
    
    for word in msg.upper().split():
        clean = re.sub(r'[^A-Z]', '', word)
        if clean and 2 <= len(clean) <= 5 and clean not in exclude:
            if clean in india_stocks:
                return clean, 'India'
            if clean in us_stocks:
                return clean, 'US'
    
    return None, market


def detect_intent(msg, market='US'):
    """Detect user intent"""
    m = msg.lower()
    
    if any(m.strip() == g for g in ['hi', 'hello', 'hey', 'thanks', 'help', 'bye']):
        return {'type': 'chat'}
    
    ticker, detected_market = find_ticker(msg, market)
    
    # Simple price query
    if any(w in m for w in ['price of', "what's the price", 'what is the price', 'how much is', 'current price']):
        if ticker:
            return {'type': 'price', 'ticker': ticker, 'market': detected_market}
    
    # Analysis request
    if any(w in m for w in ['analyze', 'analysis', 'should i buy', 'should i sell', 'verdict', 'recommendation', 'what do you think']):
        if ticker:
            return {'type': 'analyze', 'ticker': ticker, 'market': detected_market}
    
    # Gainers/Losers
    if any(w in m for w in ['gainer', 'gaining', 'best stock', 'top performer', 'top stocks', 'winners']):
        return {'type': 'gainers'}
    if any(w in m for w in ['loser', 'losing', 'worst', 'dropping', 'falling', 'down today']):
        return {'type': 'losers'}
    if any(w in m for w in ['hot', 'trending', 'moving', 'recommend', 'movers', "what's moving"]):
        return {'type': 'hot'}
    
    # If ticker found, default to analysis
    if ticker:
        return {'type': 'analyze', 'ticker': ticker, 'market': detected_market}
    
    return {'type': 'chat'}


def run_intent(intent, market='US'):
    """Execute intent"""
    t = intent.get('type')
    
    # Use detected market if available
    if intent.get('market'):
        market = intent['market']
    
    if t == 'price':
        ticker = intent['ticker']
        if market == 'India' and '.' not in ticker:
            ticker = f"{ticker}.NS"
        data = get_stock_price(ticker)
        if data:
            sym = '$' if market == 'US' else '₹'
            clr = '🟢' if data['change_pct'] >= 0 else '🔴'
            return {
                'ok': True, 'type': 'price', 'market': market,
                'msg': f"**{ticker.replace('.NS', '')}** is currently at {sym}{data['price']:,.2f} ({clr} {data['change_pct']:+.2f}% today)",
                'data': data, 'ticker': ticker
            }
        return {'ok': False, 'error': f"Could not fetch data for {ticker}"}
    
    if t == 'analyze':
        ticker = intent['ticker']
        if market == 'India' and '.' not in ticker:
            ticker = f"{ticker}.NS"
        data = get_full_data(ticker)
        if data:
            sc = calc_score(data)
            return {'ok': True, 'type': 'analysis', 'data': {**data, **sc}, 'ticker': ticker, 'market': market}
        return {'ok': False, 'error': f"Could not fetch data for {ticker}"}
    
    if t == 'gainers':
        stocks = NIFTY_50 if market == 'India' else NASDAQ_100
        results = []
        for s in stocks[:35]:
            d = get_stock_price(s)
            if d and d['change_pct'] > 0:
                results.append({'ticker': s.replace('.NS', ''), 'price': d['price'], 'change_pct': d['change_pct']})
        results.sort(key=lambda x: x['change_pct'], reverse=True)
        return {'ok': True, 'type': 'list', 'title': 'Top Gainers', 'data': results[:10], 'market': market}
    
    if t == 'losers':
        stocks = NIFTY_50 if market == 'India' else NASDAQ_100
        results = []
        for s in stocks[:35]:
            d = get_stock_price(s)
            if d and d['change_pct'] < 0:
                results.append({'ticker': s.replace('.NS', ''), 'price': d['price'], 'change_pct': d['change_pct']})
        results.sort(key=lambda x: x['change_pct'])
        return {'ok': True, 'type': 'list', 'title': 'Top Losers', 'data': results[:10], 'market': market}
    
    if t == 'hot':
        stocks = NIFTY_50 if market == 'India' else (TRENDING + NASDAQ_100[:20])
        results = []
        for s in stocks[:35]:
            d = get_stock_price(s)
            if d:
                results.append({'ticker': s.replace('.NS', ''), 'price': d['price'], 'change_pct': d['change_pct']})
        results.sort(key=lambda x: abs(x['change_pct']), reverse=True)
        return {'ok': True, 'type': 'list', 'title': 'Hot Stocks (Biggest Movers)', 'data': results[:12], 'market': market}
    
    return {'ok': False, 'type': 'chat'}


def get_ai(msg, data, history, market='US'):
    """Get AI response"""
    key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not key:
        return "Please add GROQ_API_KEY to your Streamlit secrets."
    
    try:
        client = Groq(api_key=key)
        
        sys = f"""You are Paula, an expert stock trading analyst. You have access to real-time market data.

Date: {datetime.now().strftime("%Y-%m-%d")} | Market: {market}

When analyzing stocks, provide comprehensive insights:

1. **Trading Verdict** - Start with the rating and score from the data
2. **Key Signals** - Explain the buy/sell signals from the technicals  
3. **Valuation** - Discuss P/E, analyst targets, upside potential
4. **Technicals** - RSI, moving averages, momentum, volume
5. **Risks** - List any warning signs
6. **Trading Plan** - Entry zone, stop loss, target price suggestions

Guidelines:
- Use ALL the data provided - prices, technicals, signals, warnings
- Be specific with numbers: "RSI at 42" not just "RSI is low"
- Give actionable advice: entry points, stop losses, targets
- Mention the news/catalysts if relevant
- Keep a conversational but professional tone
- For simple price queries, just give the price and a brief outlook
- NEVER say you don't have access to data - you DO have it"""

        msgs = [{"role": "system", "content": sys}]
        for h in history[-6:]:
            msgs.append({"role": h["role"], "content": h["content"]})
        
        if data:
            content = f"{msg}\n\n--- STOCK DATA ---\n{json.dumps(data, indent=2, default=str)}"
        else:
            content = msg
        msgs.append({"role": "user", "content": content})
        
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs,
            max_tokens=1500,
            temperature=0.7
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Error getting response: {str(e)[:100]}"


def main():
    st.set_page_config(page_title="Paula", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
    
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
    
    * { font-family: 'DM Sans', sans-serif; }
    
    .stApp { background: #09090b; }
    
    header, footer, #MainMenu { visibility: hidden; }
    
    .block-container { 
        max-width: 900px; 
        padding: 1.5rem 1rem 4rem 1rem;
    }
    
    h1, h2, h3 { color: #fafafa !important; font-weight: 600 !important; }
    p, span, div, label { color: #a1a1aa !important; }
    
    .stChatMessage { 
        background: #18181b !important; 
        border: 1px solid #27272a !important; 
        border-radius: 12px !important;
        padding: 1rem !important;
    }
    .stChatMessage p, .stChatMessage span, .stChatMessage li { 
        color: #e4e4e7 !important; 
    }
    
    .stChatInputContainer {
        padding-bottom: 20px;
    }
    
    .stTextInput > div > div > input,
    .stChatInput > div > div > textarea { 
        background: #18181b !important; 
        border: 1px solid #27272a !important; 
        border-radius: 12px !important;
        color: #fafafa !important;
        font-size: 1rem !important;
    }
    
    .stButton > button { 
        background: #27272a !important; 
        color: #fafafa !important; 
        border: 1px solid #3f3f46 !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
    }
    .stButton > button:hover { 
        background: #3f3f46 !important;
        border-color: #52525b !important;
    }
    
    .stSelectbox > div > div { 
        background: #18181b !important; 
        border: 1px solid #27272a !important;
        border-radius: 8px !important;
    }
    
    .stExpander { 
        background: #18181b !important; 
        border: 1px solid #27272a !important;
        border-radius: 8px !important;
    }
    
    .stDataFrame {
        background: #18181b !important;
        border-radius: 8px !important;
    }
    .stDataFrame td, .stDataFrame th {
        background: #18181b !important;
        color: #e4e4e7 !important;
        border-color: #27272a !important;
    }
    
    hr { border-color: #27272a !important; margin: 1rem 0 !important; }
    
    .stAudio { margin-top: 10px; }
    
    /* Voice input button styling */
    .stAudioInput > div { background: transparent !important; }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize state
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'market' not in st.session_state:
        st.session_state.market = 'US'
    if 'show_charts' not in st.session_state:
        st.session_state.show_charts = True
    
    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        icon = "🇺🇸" if st.session_state.market == 'US' else "🇮🇳"
        st.markdown(f"## Paula {icon}")
        st.caption("Your stock analysis assistant • Ask about any stock")
    
    with col2:
        with st.expander("⚙️ Settings"):
            new_market = st.selectbox(
                "Market",
                ['US', 'India'],
                index=0 if st.session_state.market == 'US' else 1,
                help="Auto-detects from your message"
            )
            if new_market != st.session_state.market:
                st.session_state.market = new_market
            
            st.session_state.show_charts = st.checkbox("Show charts", value=st.session_state.show_charts)
            
            if st.button("🗑️ Clear chat"):
                st.session_state.messages = []
                st.rerun()
    
    st.markdown("---")
    
    # Chat messages
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            
            # Show chart for assistant messages
            if m["role"] == "assistant" and m.get("chart") and st.session_state.show_charts:
                ch = make_chart(m["chart"])
                if ch:
                    st.plotly_chart(ch, use_container_width=True)
            
            # Show table
            if m["role"] == "assistant" and m.get("table"):
                st.dataframe(pd.DataFrame(m["table"]), use_container_width=True, hide_index=True)
    
    # Voice input
    try:
        from streamlit_mic_recorder import mic_recorder
        
        col_input, col_mic = st.columns([6, 1])
        
        with col_mic:
            audio = mic_recorder(
                start_prompt="🎤",
                stop_prompt="⏹️",
                just_once=True,
                use_container_width=True,
                key="mic"
            )
        
        # Process voice input
        voice_text = None
        if audio and audio.get('bytes'):
            try:
                key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
                if key:
                    client = Groq(api_key=key)
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        f.write(audio['bytes'])
                        f.flush()
                        with open(f.name, "rb") as audio_file:
                            transcription = client.audio.transcriptions.create(
                                file=(f.name, audio_file.read()),
                                model="whisper-large-v3"
                            )
                            voice_text = transcription.text
            except Exception as e:
                st.error(f"Voice error: {str(e)[:50]}")
    except ImportError:
        voice_text = None
        col_input = st.container()
    
    # Text input
    prompt = st.chat_input("Ask about any stock... (e.g., 'analyze NVDA' or 'top gainers')")
    
    # Use voice text if available
    if voice_text:
        prompt = voice_text
        st.toast(f"🎤 {voice_text}")
    
    if prompt:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                # Auto-detect market from message
                detected = auto_detect_market(prompt)
                if detected:
                    st.session_state.market = detected
                
                market = st.session_state.market
                
                # Process intent
                intent = detect_intent(prompt, market)
                res = run_intent(intent, market)
                
                # Update market if detected from ticker
                if res.get('market'):
                    st.session_state.market = res['market']
                    market = res['market']
                
                chart_ticker = None
                table_data = None
                
                if res.get('ok'):
                    if res['type'] == 'price':
                        chart_ticker = res['ticker']
                        resp = res['msg']
                    
                    elif res['type'] == 'analysis':
                        chart_ticker = res['ticker']
                        resp = get_ai(prompt, res['data'], st.session_state.messages, market)
                    
                    elif res['type'] == 'list':
                        table_data = res['data'].copy()
                        sym = '₹' if market == 'India' else '$'
                        for i in table_data:
                            clr = '🟢' if i['change_pct'] >= 0 else '🔴'
                            i['Change'] = f"{clr} {i['change_pct']:+.2f}%"
                            i['Price'] = f"{sym}{i['price']:,.2f}"
                            del i['change_pct']
                            del i['price']
                        resp = f"**{res['title']}** ({market} Market)"
                    
                    else:
                        resp = get_ai(prompt, None, st.session_state.messages, market)
                
                elif res.get('error'):
                    resp = f"⚠️ {res['error']}"
                
                else:
                    resp = get_ai(prompt, None, st.session_state.messages, market)
                
                st.markdown(resp)
                
                # Show chart - ALWAYS try for stock queries
                if chart_ticker and st.session_state.show_charts:
                    with st.spinner("Loading chart..."):
                        ch = make_chart(chart_ticker)
                        if ch:
                            st.plotly_chart(ch, use_container_width=True)
                        else:
                            st.caption(f"📊 Chart unavailable for {chart_ticker}")
                
                # Show table
                if table_data:
                    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
        
        # Save message
        st.session_state.messages.append({
            "role": "assistant",
            "content": resp,
            "chart": chart_ticker,
            "table": table_data
        })
    
    # Footer
    st.markdown("---")
    st.caption("Not financial advice. Always do your own research.")


if __name__ == "__main__":
    main()
