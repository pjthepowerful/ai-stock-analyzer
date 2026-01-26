import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import json
import os
from dotenv import load_dotenv
import re
from groq import Groq
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests

warnings.filterwarnings('ignore')
load_dotenv()

# ==================== NEWS ====================
def get_stock_news(ticker, limit=5):
    """Fetch recent news for a stock"""
    display_ticker = ticker.replace('.NS', '').replace('.BO', '')
    
    # Try yfinance news first (most reliable)
    try:
        stock = yf.Ticker(ticker if '.NS' in ticker or '.BO' in ticker else display_ticker)
        news = stock.news
        if news:
            return [{
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'publisher': item.get('publisher', ''),
                'date': datetime.fromtimestamp(item.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M') if item.get('providerPublishTime') else ''
            } for item in news[:limit]]
    except:
        pass
    
    return []

def get_market_news(market='US', limit=5):
    """Get general market news"""
    tickers_to_try = ['^GSPC', 'SPY', 'AAPL'] if market == 'US' else ['^NSEI', 'RELIANCE.NS', 'TCS.NS']
    
    for ticker in tickers_to_try:
        news = get_stock_news(ticker, limit)
        if news:
            return news
    return []

def format_news_for_ai(news_items):
    """Format news items for AI context"""
    if not news_items:
        return "No recent news available."
    
    formatted = []
    for item in news_items[:5]:
        source = f" ({item['publisher']})" if item.get('publisher') else ""
        formatted.append(f"• {item['title']}{source}")
    return "\n".join(formatted)

# ==================== SMART STOCK DISCOVERY ====================
def discover_trending_stocks():
    """Discover trending stocks from market news and gainers - not just fixed lists"""
    market = st.session_state.get('market', 'US')
    discovered = []
    
    # 1. Get stocks from market movers/gainers via yfinance
    try:
        if market == 'US':
            # Get day gainers - these are stocks moving NOW
            gainers = yf.Tickers("^GSPC ^NDX ^DJI SPY QQQ").tickers
            
            # Try to get trending tickers from major indices movement
            for idx_ticker in ['^GSPC', '^NDX']:
                try:
                    idx = yf.Ticker(idx_ticker)
                    # Get news which often mentions hot stocks
                    news = idx.news or []
                    for item in news[:10]:
                        # Extract ticker symbols from news titles
                        title = item.get('title', '')
                        # Look for stock mentions in parentheses like (AAPL) or (NVDA)
                        import re
                        tickers_in_news = re.findall(r'\(([A-Z]{2,5})\)', title)
                        for t in tickers_in_news:
                            if t not in discovered and len(t) >= 2:
                                discovered.append(t)
                except:
                    pass
        else:
            # Indian market
            for idx_ticker in ['^NSEI', '^BSESN']:
                try:
                    idx = yf.Ticker(idx_ticker)
                    news = idx.news or []
                    for item in news[:10]:
                        title = item.get('title', '')
                        # Indian tickers often mentioned directly
                        for indian_stock in NIFTY_50 + TRENDING_INDIA:
                            name = indian_stock.replace('.NS', '').replace('.BO', '')
                            if name.lower() in title.lower():
                                if indian_stock not in discovered:
                                    discovered.append(indian_stock)
                except:
                    pass
    except:
        pass
    
    return discovered[:20]

def get_market_movers():
    """Get today's biggest movers from a quick scan"""
    market = st.session_state.get('market', 'US')
    
    # Use a smaller, high-quality list for speed
    if market == 'US':
        # Mix of large caps and known volatile stocks
        quick_scan = ['NVDA', 'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'AMD', 'SMCI', 
                      'PLTR', 'COIN', 'MSTR', 'ARM', 'AVGO', 'MU', 'INTC', 'CRM', 'ORCL',
                      'NFLX', 'DIS', 'PYPL', 'SQ', 'SHOP', 'SNOW', 'NET', 'CRWD', 'ZS',
                      'RIVN', 'LCID', 'NIO', 'F', 'GM', 'BA', 'CAT', 'DE', 'UNH', 'JNJ',
                      'JPM', 'BAC', 'GS', 'V', 'MA', 'WMT', 'COST', 'HD', 'LOW']
    else:
        quick_scan = [s.replace('.NS', '') for s in NIFTY_50[:30]]
    
    movers = []
    for ticker in quick_scan:
        try:
            full_ticker = f"{ticker}.NS" if market == 'India' else ticker
            stock = yf.Ticker(full_ticker)
            fast = stock.fast_info
            
            price = fast.get('lastPrice') or fast.get('regularMarketPrice')
            prev = fast.get('previousClose')
            
            if price and prev and prev > 0:
                change_pct = ((price - prev) / prev) * 100
                movers.append({
                    'ticker': ticker,
                    'full_ticker': full_ticker,
                    'price': price,
                    'change_pct': change_pct
                })
        except:
            continue
    
    # Sort by absolute change (biggest movers either direction)
    movers.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    return movers

def smart_scan_stocks(scan_type='hot'):
    """
    Smart scanning that discovers stocks rather than just checking fixed lists.
    scan_type: 'hot' (trending), 'gainers', 'losers', 'news'
    """
    market = st.session_state.get('market', 'US')
    results = []
    
    status = st.empty()
    progress = st.progress(0)
    
    status.text("🔍 Finding market movers...")
    progress.progress(0.2)
    
    # Step 1: Get today's movers
    movers = get_market_movers()
    progress.progress(0.4)
    
    # Step 2: Discover stocks from news
    status.text("📰 Scanning news for trending stocks...")
    news_stocks = discover_trending_stocks()
    progress.progress(0.6)
    
    # Combine and dedupe
    all_tickers = []
    seen = set()
    
    # Add movers first (sorted by movement)
    for m in movers:
        if m['ticker'] not in seen:
            all_tickers.append(m)
            seen.add(m['ticker'])
    
    # Add news-discovered stocks
    for t in news_stocks:
        clean = t.replace('.NS', '').replace('.BO', '')
        if clean not in seen:
            all_tickers.append({'ticker': clean, 'full_ticker': t, 'price': None, 'change_pct': None})
            seen.add(clean)
    
    progress.progress(0.7)
    status.text("📊 Analyzing top candidates...")
    
    # Step 3: Get full data for top candidates
    candidates = all_tickers[:25]  # Limit for speed
    
    for i, stock in enumerate(candidates):
        progress.progress(0.7 + (0.3 * (i + 1) / len(candidates)))
        
        try:
            ticker = stock['full_ticker'] if stock.get('full_ticker') else stock['ticker']
            if market == 'India' and '.NS' not in ticker and '.BO' not in ticker:
                ticker = f"{stock['ticker']}.NS"
            
            data = get_live_stock_data(ticker)
            if not data:
                continue
            
            perf = get_performance_data(ticker)
            
            currency = '₹' if market == 'India' else '$'
            
            result = {
                'ticker': data['display_ticker'],
                'full_ticker': ticker,
                'name': data['name'][:25] if data['name'] else data['display_ticker'],
                'price': data['price'],
                'price_fmt': f"{currency}{data['price']:,.2f}",
                'change_pct': data['change_pct'],
                'perf_1w': perf.get('1w') if perf else None,
                'perf_1m': perf.get('1m') if perf else None,
                'perf_ytd': perf.get('ytd') if perf else None,
                'sector': data['sector'],
                'market_cap': data['market_cap'],
                'market_cap_fmt': data['market_cap_fmt'],
                'pe_ratio': data['pe_ratio'],
                'recommendation': data.get('recommendation'),
            }
            results.append(result)
        except:
            continue
    
    progress.empty()
    status.empty()
    
    # Sort based on scan type
    if scan_type == 'gainers':
        results.sort(key=lambda x: x['change_pct'] or 0, reverse=True)
        results = [r for r in results if (r['change_pct'] or 0) > 0]
    elif scan_type == 'losers':
        results.sort(key=lambda x: x['change_pct'] or 0)
        results = [r for r in results if (r['change_pct'] or 0) < 0]
    elif scan_type == 'hot':
        # Hot = biggest absolute movers
        results.sort(key=lambda x: abs(x['change_pct'] or 0), reverse=True)
    elif scan_type == 'momentum':
        # Best weekly/monthly performance
        results.sort(key=lambda x: (x['perf_1w'] or 0) + (x['perf_1m'] or 0), reverse=True)
    
    return results[:15]

def scan_from_news():
    """Find stocks being mentioned in news with sentiment"""
    market = st.session_state.get('market', 'US')
    
    status = st.empty()
    progress = st.progress(0)
    status.text("📰 Scanning market news...")
    
    # Get news from major sources
    news_sources = ['^GSPC', 'SPY', '^NDX'] if market == 'US' else ['^NSEI', '^BSESN']
    
    all_news = []
    mentioned_stocks = {}
    
    for source in news_sources:
        try:
            ticker = yf.Ticker(source)
            news = ticker.news or []
            for item in news[:15]:
                title = item.get('title', '')
                all_news.append(title)
                
                # Find stock mentions
                tickers_found = re.findall(r'\b([A-Z]{2,5})\b', title)
                exclude = {'CEO', 'IPO', 'ETF', 'NYSE', 'SEC', 'FDA', 'AI', 'US', 'UK', 'GDP', 'CPI', 'FED', 'THE', 'FOR', 'AND'}
                
                for t in tickers_found:
                    if t not in exclude and len(t) >= 2:
                        if t not in mentioned_stocks:
                            mentioned_stocks[t] = {'count': 0, 'titles': []}
                        mentioned_stocks[t]['count'] += 1
                        mentioned_stocks[t]['titles'].append(title[:100])
        except:
            continue
    
    progress.progress(0.5)
    status.text("🔍 Analyzing mentioned stocks...")
    
    # Get data for most mentioned stocks
    sorted_mentions = sorted(mentioned_stocks.items(), key=lambda x: x[1]['count'], reverse=True)
    
    results = []
    for ticker, info in sorted_mentions[:15]:
        progress.progress(0.5 + (0.5 * len(results) / 15))
        
        try:
            full_ticker = f"{ticker}.NS" if market == 'India' else ticker
            data = get_live_stock_data(full_ticker)
            
            if not data:
                continue
            
            # Analyze sentiment of news mentioning this stock
            sentiment = analyze_news_sentiment([{'title': t} for t in info['titles']])
            
            currency = '₹' if market == 'India' else '$'
            results.append({
                'ticker': data['display_ticker'],
                'full_ticker': full_ticker,
                'price_fmt': f"{currency}{data['price']:,.2f}",
                'change_pct': data['change_pct'],
                'mentions': info['count'],
                'sentiment': 'Positive' if sentiment > 0.1 else ('Negative' if sentiment < -0.1 else 'Neutral'),
                'sentiment_score': sentiment,
                'sample_news': info['titles'][0] if info['titles'] else '',
                'sector': data['sector'],
            })
        except:
            continue
    
    progress.empty()
    status.empty()
    
    # Sort by mentions and positive sentiment
    results.sort(key=lambda x: (x['mentions'], x['sentiment_score']), reverse=True)
    
    return results

def screen_smart(scan_type='hot'):
    """Smart screening that uses discovery instead of fixed lists"""
    market = st.session_state.get('market', 'US')
    
    if scan_type == 'news':
        stocks = scan_from_news()
        if not stocks:
            return {"success": False, "message": "Couldn't find stocks in news"}
        
        table = []
        found_tickers = []
        for s in stocks:
            found_tickers.append(s['full_ticker'])
            color = "🟢" if s['change_pct'] >= 0 else "🔴"
            table.append({
                "Ticker": s['ticker'],
                "Price": s['price_fmt'],
                "Change": f"{color} {s['change_pct']:+.1f}%",
                "News Mentions": s['mentions'],
                "Sentiment": s['sentiment'],
            })
        
        st.session_state.charts_to_display = found_tickers[:3]
        
        return {
            "success": True,
            "screen_type": "Stocks in the News",
            "found": len(table),
            "table": table,
            "description": "Stocks being mentioned in today's market news"
        }
    
    else:
        stocks = smart_scan_stocks(scan_type)
        if not stocks:
            return {"success": False, "message": f"No {scan_type} stocks found"}
        
        table = []
        found_tickers = []
        
        def fmt_perf(val):
            if val is None: return "N/A"
            color = "🟢" if val >= 0 else "🔴"
            return f"{color} {val:+.1f}%"
        
        for s in stocks:
            found_tickers.append(s['full_ticker'])
            table.append({
                "Ticker": s['ticker'],
                "Price": s['price_fmt'],
                "Today": fmt_perf(s['change_pct']),
                "1W": fmt_perf(s['perf_1w']),
                "1M": fmt_perf(s['perf_1m']),
            })
        
        st.session_state.charts_to_display = found_tickers[:3]
        
        # Get some market news for context
        market_news = get_market_news(market, limit=5)
        
        type_names = {
            'hot': 'Hot Stocks (Biggest Movers)',
            'gainers': "Today's Gainers",
            'losers': "Today's Losers", 
            'momentum': 'Momentum Stocks'
        }
        
        return {
            "success": True,
            "screen_type": type_names.get(scan_type, scan_type.title()),
            "found": len(table),
            "table": table,
            "market_news": format_news_for_ai(market_news),
            "description": "Dynamically discovered from market activity and news"
        }
def get_advanced_technicals(ticker, period="3mo"):
    """Calculate advanced technical indicators for trading signals"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty or len(hist) < 50:
            return None
        
        df = hist.copy()
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume']
        
        # Moving Averages
        df['SMA_20'] = close.rolling(window=20).mean()
        df['SMA_50'] = close.rolling(window=50).mean()
        df['SMA_200'] = close.rolling(window=200).mean() if len(close) >= 200 else None
        df['EMA_9'] = close.ewm(span=9, adjust=False).mean()
        df['EMA_21'] = close.ewm(span=21, adjust=False).mean()
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        # Bollinger Bands
        df['BB_Middle'] = close.rolling(window=20).mean()
        bb_std = close.rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        df['BB_Position'] = (close - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
        
        # Average True Range (ATR) for volatility
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(window=14).mean()
        df['ATR_Percent'] = (df['ATR'] / close) * 100
        
        # Volume Analysis
        df['Volume_SMA'] = volume.rolling(window=20).mean()
        df['Volume_Ratio'] = volume / df['Volume_SMA']
        
        # Stochastic Oscillator
        lowest_low = low.rolling(window=14).min()
        highest_high = high.rolling(window=14).max()
        df['Stoch_K'] = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
        
        # Price momentum
        df['ROC_5'] = ((close - close.shift(5)) / close.shift(5)) * 100  # 5-day rate of change
        df['ROC_20'] = ((close - close.shift(20)) / close.shift(20)) * 100  # 20-day rate of change
        
        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        return {
            'current_price': latest['Close'],
            'sma_20': latest['SMA_20'],
            'sma_50': latest['SMA_50'],
            'ema_9': latest['EMA_9'],
            'ema_21': latest['EMA_21'],
            'rsi': latest['RSI'],
            'macd': latest['MACD'],
            'macd_signal': latest['MACD_Signal'],
            'macd_hist': latest['MACD_Hist'],
            'macd_hist_prev': prev['MACD_Hist'],
            'bb_upper': latest['BB_Upper'],
            'bb_lower': latest['BB_Lower'],
            'bb_position': latest['BB_Position'],
            'atr': latest['ATR'],
            'atr_percent': latest['ATR_Percent'],
            'volume_ratio': latest['Volume_Ratio'],
            'stoch_k': latest['Stoch_K'],
            'stoch_d': latest['Stoch_D'],
            'roc_5': latest['ROC_5'],
            'roc_20': latest['ROC_20'],
            'price_vs_sma20': ((latest['Close'] - latest['SMA_20']) / latest['SMA_20']) * 100,
            'price_vs_sma50': ((latest['Close'] - latest['SMA_50']) / latest['SMA_50']) * 100,
            'ema_crossover': 'bullish' if latest['EMA_9'] > latest['EMA_21'] and prev['EMA_9'] <= prev['EMA_21'] else 
                           ('bearish' if latest['EMA_9'] < latest['EMA_21'] and prev['EMA_9'] >= prev['EMA_21'] else 'none'),
            'macd_crossover': 'bullish' if latest['MACD'] > latest['MACD_Signal'] and prev['MACD'] <= prev['MACD_Signal'] else
                            ('bearish' if latest['MACD'] < latest['MACD_Signal'] and prev['MACD'] >= prev['MACD_Signal'] else 'none'),
        }
    except Exception as e:
        return None

def get_earnings_data(ticker):
    """Get earnings and financial calendar data"""
    try:
        stock = yf.Ticker(ticker)
        
        # Get earnings dates
        try:
            calendar = stock.calendar
            earnings_date = calendar.get('Earnings Date', [None])[0] if calendar else None
        except:
            earnings_date = None
        
        # Get earnings history
        try:
            earnings_hist = stock.earnings_history
            if earnings_hist is not None and len(earnings_hist) > 0:
                recent_earnings = []
                for _, row in earnings_hist.tail(4).iterrows():
                    surprise_pct = row.get('surprisePercent', 0)
                    recent_earnings.append({
                        'date': str(row.name)[:10] if hasattr(row, 'name') else 'N/A',
                        'actual': row.get('epsActual', 'N/A'),
                        'estimate': row.get('epsEstimate', 'N/A'),
                        'surprise': f"{surprise_pct*100:+.1f}%" if surprise_pct else 'N/A'
                    })
            else:
                recent_earnings = []
        except:
            recent_earnings = []
        
        # Get quarterly financials
        try:
            quarterly = stock.quarterly_financials
            if quarterly is not None and not quarterly.empty:
                revenue_growth = None
                if 'Total Revenue' in quarterly.index and len(quarterly.columns) >= 4:
                    recent_rev = quarterly.loc['Total Revenue'].iloc[0]
                    year_ago_rev = quarterly.loc['Total Revenue'].iloc[3]
                    if recent_rev and year_ago_rev:
                        revenue_growth = ((recent_rev - year_ago_rev) / year_ago_rev) * 100
            else:
                revenue_growth = None
        except:
            revenue_growth = None
        
        return {
            'next_earnings': str(earnings_date)[:10] if earnings_date else 'N/A',
            'recent_earnings': recent_earnings,
            'revenue_growth_yoy': revenue_growth
        }
    except:
        return None

def calculate_trading_score(data, technicals, earnings, news_sentiment):
    """Calculate comprehensive trading score for swing/short-term trading"""
    
    score = 0
    signals = []
    warnings = []
    
    # ===== TECHNICAL SIGNALS (40 points max) =====
    if technicals:
        # RSI Analysis (8 points)
        rsi = technicals.get('rsi', 50)
        if 30 <= rsi <= 40:
            score += 8
            signals.append("RSI oversold bounce zone (30-40) - strong buy signal")
        elif 40 < rsi <= 60:
            score += 5
            signals.append("RSI neutral (40-60) - healthy momentum")
        elif 60 < rsi <= 70:
            score += 3
            signals.append("RSI elevated (60-70) - momentum but watch for pullback")
        elif rsi > 70:
            score += 0
            warnings.append("RSI overbought (>70) - potential pullback risk")
        elif rsi < 30:
            score += 4
            signals.append("RSI deeply oversold (<30) - could bounce but risky")
        
        # MACD Analysis (8 points)
        macd_cross = technicals.get('macd_crossover', 'none')
        macd_hist = technicals.get('macd_hist', 0)
        if macd_cross == 'bullish':
            score += 8
            signals.append("MACD bullish crossover - strong buy signal")
        elif macd_hist > 0 and technicals.get('macd_hist_prev', 0) < macd_hist:
            score += 5
            signals.append("MACD histogram expanding positive - momentum building")
        elif macd_cross == 'bearish':
            warnings.append("MACD bearish crossover - caution")
        
        # EMA Crossover (6 points)
        ema_cross = technicals.get('ema_crossover', 'none')
        if ema_cross == 'bullish':
            score += 6
            signals.append("EMA 9/21 bullish crossover - short-term buy signal")
        elif technicals.get('ema_9', 0) > technicals.get('ema_21', 0):
            score += 3
            signals.append("Price above short-term EMAs - uptrend intact")
        elif ema_cross == 'bearish':
            warnings.append("EMA bearish crossover - short-term weakness")
        
        # Trend Analysis - Price vs SMAs (8 points)
        price_vs_20 = technicals.get('price_vs_sma20', 0)
        price_vs_50 = technicals.get('price_vs_sma50', 0)
        if price_vs_20 > 0 and price_vs_50 > 0:
            score += 6
            signals.append("Price above 20 & 50 SMA - strong uptrend")
        elif price_vs_20 > 0:
            score += 3
            signals.append("Price above 20 SMA - short-term uptrend")
        elif price_vs_20 < -5 and price_vs_50 < -10:
            score += 2
            signals.append("Price well below SMAs - potential bounce play")
        
        # Bollinger Band Position (5 points)
        bb_pos = technicals.get('bb_position', 0.5)
        if 0.2 <= bb_pos <= 0.4:
            score += 5
            signals.append("Near lower Bollinger Band - potential bounce")
        elif 0.4 < bb_pos <= 0.6:
            score += 3
            signals.append("Middle of Bollinger Bands - neutral")
        elif bb_pos > 0.9:
            warnings.append("At upper Bollinger Band - extended, may pullback")
        
        # Volume Confirmation (5 points)
        vol_ratio = technicals.get('volume_ratio', 1)
        if vol_ratio > 1.5:
            score += 5
            signals.append(f"High volume ({vol_ratio:.1f}x avg) - strong conviction")
        elif vol_ratio > 1.2:
            score += 3
            signals.append("Above average volume - good participation")
        elif vol_ratio < 0.7:
            warnings.append("Below average volume - weak conviction")
    
    # ===== FUNDAMENTAL SIGNALS (30 points max) =====
    if data:
        # Valuation (10 points)
        pe = data.get('pe_ratio')
        forward_pe = data.get('forward_pe')
        peg = data.get('peg_ratio')
        
        if forward_pe and pe and forward_pe < pe * 0.7:
            score += 8
            signals.append(f"Forward P/E ({forward_pe:.1f}) much lower than trailing ({pe:.1f}) - earnings growth expected")
        elif pe and 10 < pe < 25:
            score += 5
            signals.append(f"Reasonable P/E of {pe:.1f}")
        elif pe and pe > 40:
            warnings.append(f"High P/E of {pe:.1f} - expensive valuation")
        
        if peg and 0 < peg < 1.5:
            score += 4
            signals.append(f"Attractive PEG ratio of {peg:.2f}")
        
        # Analyst Sentiment (10 points)
        recommendation = data.get('recommendation', '')
        target_price = data.get('target_price')
        current_price = data.get('price')
        
        if recommendation in ['strong_buy', 'buy']:
            score += 6
            signals.append(f"Analyst rating: {recommendation.replace('_', ' ').title()}")
        
        if target_price and current_price:
            try:
                current_val = float(str(current_price).replace('$', '').replace('₹', '').replace(',', ''))
                upside = ((target_price - current_val) / current_val) * 100
                if upside > 20:
                    score += 4
                    signals.append(f"Analyst target implies {upside:.0f}% upside")
                elif upside > 10:
                    score += 2
                    signals.append(f"Analyst target implies {upside:.0f}% upside")
                elif upside < 0:
                    warnings.append(f"Trading above analyst target by {abs(upside):.0f}%")
            except:
                pass
        
        # Growth Metrics (10 points)
        revenue_growth = data.get('revenue_growth')
        earnings_growth = data.get('earnings_growth')
        roe = data.get('roe')
        
        if revenue_growth and revenue_growth > 0.20:
            score += 4
            signals.append(f"Strong revenue growth: {revenue_growth*100:.0f}%")
        elif revenue_growth and revenue_growth > 0.10:
            score += 2
            signals.append(f"Solid revenue growth: {revenue_growth*100:.0f}%")
        
        if roe and roe > 0.20:
            score += 3
            signals.append(f"Excellent ROE: {roe*100:.0f}%")
        elif roe and roe > 0.15:
            score += 2
    
    # ===== EARNINGS SIGNALS (15 points max) =====
    if earnings:
        recent = earnings.get('recent_earnings', [])
        if recent:
            beats = sum(1 for e in recent if e.get('surprise', '').startswith('+'))
            if beats >= 3:
                score += 10
                signals.append(f"Beat earnings {beats}/4 recent quarters - consistent performer")
            elif beats >= 2:
                score += 6
                signals.append(f"Beat earnings {beats}/4 recent quarters")
            
            # Check most recent surprise magnitude
            if recent and recent[0].get('surprise'):
                try:
                    surprise_str = recent[0]['surprise'].replace('%', '').replace('+', '')
                    surprise_val = float(surprise_str)
                    if surprise_val > 10:
                        score += 5
                        signals.append(f"Last earnings beat by {surprise_val:.0f}% - strong surprise")
                except:
                    pass
        
        # Upcoming earnings catalyst
        next_earnings = earnings.get('next_earnings', 'N/A')
        if next_earnings != 'N/A':
            signals.append(f"Next earnings: {next_earnings}")
    
    # ===== NEWS SENTIMENT (15 points max) =====
    if news_sentiment:
        if news_sentiment > 0.5:
            score += 10
            signals.append("Strong positive news sentiment")
        elif news_sentiment > 0.2:
            score += 6
            signals.append("Positive news sentiment")
        elif news_sentiment < -0.3:
            warnings.append("Negative news sentiment")
    
    # Calculate final rating
    max_score = 100
    pct = (score / max_score) * 100
    
    if pct >= 70:
        rating = "🟢 STRONG BUY"
        action = "High conviction setup - consider entering position"
    elif pct >= 55:
        rating = "🟢 BUY"
        action = "Good setup - favorable risk/reward"
    elif pct >= 40:
        rating = "🟡 HOLD/ACCUMULATE"
        action = "Neutral - wait for better entry or add to existing position"
    elif pct >= 25:
        rating = "🟠 CAUTION"
        action = "Weak setup - avoid new positions"
    else:
        rating = "🔴 AVOID"
        action = "Poor setup - stay away or consider shorting"
    
    return {
        'score': score,
        'max_score': max_score,
        'percentage': pct,
        'rating': rating,
        'action': action,
        'signals': signals,
        'warnings': warnings
    }

def analyze_news_sentiment(news_items):
    """Simple sentiment analysis on news headlines"""
    if not news_items:
        return 0
    
    positive_words = ['surge', 'jump', 'soar', 'rally', 'beat', 'exceed', 'upgrade', 'buy', 'bullish',
                     'record', 'high', 'growth', 'profit', 'gain', 'positive', 'strong', 'boost',
                     'outperform', 'success', 'win', 'breakthrough', 'innovation', 'demand', 'raise']
    
    negative_words = ['fall', 'drop', 'plunge', 'crash', 'miss', 'downgrade', 'sell', 'bearish',
                     'low', 'loss', 'decline', 'negative', 'weak', 'cut', 'concern', 'risk',
                     'underperform', 'fail', 'lawsuit', 'investigation', 'recall', 'warning']
    
    score = 0
    for item in news_items:
        title = item.get('title', '').lower()
        for word in positive_words:
            if word in title:
                score += 1
        for word in negative_words:
            if word in title:
                score -= 1
    
    # Normalize to -1 to 1 range
    max_possible = len(news_items) * 2
    return score / max_possible if max_possible > 0 else 0

def get_performance_data(ticker):
    """Get stock performance over different time periods"""
    try:
        stock = yf.Ticker(ticker)
        
        # Get historical data
        hist_1y = stock.history(period="1y")
        if hist_1y.empty or len(hist_1y) < 5:
            return None
        
        current_price = hist_1y['Close'].iloc[-1]
        if current_price is None or current_price <= 0:
            return None
        
        # Calculate performance for different periods
        performance = {}
        
        def safe_calc_return(current, past):
            """Safely calculate return percentage"""
            if past is None or past <= 0:
                return None
            return ((current - past) / past) * 100
        
        # 1 Week
        if len(hist_1y) >= 5:
            week_ago = hist_1y['Close'].iloc[-5]
            performance['1w'] = safe_calc_return(current_price, week_ago)
        
        # 1 Month (~21 trading days)
        if len(hist_1y) >= 21:
            month_ago = hist_1y['Close'].iloc[-21]
            performance['1m'] = safe_calc_return(current_price, month_ago)
        
        # 3 Months (~63 trading days)
        if len(hist_1y) >= 63:
            three_month_ago = hist_1y['Close'].iloc[-63]
            performance['3m'] = safe_calc_return(current_price, three_month_ago)
        
        # 6 Months (~126 trading days)
        if len(hist_1y) >= 126:
            six_month_ago = hist_1y['Close'].iloc[-126]
            performance['6m'] = safe_calc_return(current_price, six_month_ago)
        
        # YTD
        try:
            year_start = datetime(datetime.now().year, 1, 1)
            # Convert index to timezone-naive for comparison
            hist_dates = hist_1y.index.tz_localize(None) if hist_1y.index.tz else hist_1y.index
            ytd_mask = hist_dates >= year_start
            ytd_data = hist_1y[ytd_mask]
            if len(ytd_data) > 0:
                ytd_start = ytd_data['Close'].iloc[0]
                performance['ytd'] = safe_calc_return(current_price, ytd_start)
        except Exception:
            pass
        
        # 1 Year
        if len(hist_1y) >= 200:  # Changed from 252 to be more lenient
            year_ago = hist_1y['Close'].iloc[0]
            performance['1y'] = safe_calc_return(current_price, year_ago)
        
        return performance
    except Exception:
        return None

def scan_hot_stocks(timeframe='1m', min_gain=10, limit=20):
    """Scan for hot stocks with strong recent performance"""
    market = st.session_state.get('market', 'US')
    
    # Use smaller list for speed - prioritize trending stocks
    if market == 'US':
        stocks_to_scan = TRENDING_US[:50] + NASDAQ_100[:30]  # 80 stocks max
    else:
        stocks_to_scan = TRENDING_INDIA[:30] + NIFTY_50[:20]  # 50 stocks max
    
    # Remove duplicates while preserving order
    stocks_to_scan = list(dict.fromkeys(stocks_to_scan))
    
    results = []
    progress = st.progress(0)
    status = st.empty()
    
    failed_count = 0
    for i, ticker in enumerate(stocks_to_scan):
        progress.progress((i + 1) / len(stocks_to_scan))
        status.text(f"Scanning {ticker}... ({i+1}/{len(stocks_to_scan)})")
        
        try:
            data = get_live_stock_data(ticker)
            if not data:
                failed_count += 1
                continue
            
            perf = get_performance_data(ticker)
            if not perf:
                failed_count += 1
                continue
            
            # Get the relevant timeframe performance
            gain = perf.get(timeframe)
            if gain is None:
                continue
            
            # Filter by minimum gain
            if gain >= min_gain:
                currency = '₹' if data['market'] == 'India' else '$'
                results.append({
                    'ticker': data['display_ticker'],
                    'full_ticker': ticker,
                    'name': data['name'][:20] if data['name'] else data['display_ticker'],
                    'price': data['price'],
                    'price_fmt': f"{currency}{data['price']:,.2f}",
                    'change_today': data['change_pct'],
                    'perf_1w': perf.get('1w'),
                    'perf_1m': perf.get('1m'),
                    'perf_3m': perf.get('3m'),
                    'perf_ytd': perf.get('ytd'),
                    'perf_1y': perf.get('1y'),
                    'target_gain': gain,
                    'sector': data['sector'],
                    'market_cap': data['market_cap'],
                    'market_cap_fmt': data['market_cap_fmt'],
                    'pe_ratio': data['pe_ratio'],
                    'recommendation': data['recommendation'],
                })
        except Exception:
            failed_count += 1
            continue
    
    progress.empty()
    status.empty()
    
    # Show warning if many failed
    if failed_count > len(stocks_to_scan) * 0.5:
        st.warning(f"⚠️ {failed_count} stocks couldn't be fetched. Data may be incomplete.")
    
    # Sort by the target timeframe gain
    results.sort(key=lambda x: x['target_gain'], reverse=True)
    
    return results[:limit]

def screen_by_performance(timeframe='1m', direction='gainers'):
    """Screen stocks by performance over a timeframe"""
    market = st.session_state.get('market', 'US')
    
    # Determine minimum gain based on direction
    if direction == 'gainers':
        min_gain = 5  # At least 5% gain
        stocks = scan_hot_stocks(timeframe, min_gain=min_gain, limit=20)
    else:  # losers
        stocks = scan_hot_stocks(timeframe, min_gain=-100, limit=50)  # Get all, then filter
        stocks = [s for s in stocks if s['target_gain'] < -5]  # At least 5% loss
        stocks.sort(key=lambda x: x['target_gain'])  # Worst first
        stocks = stocks[:20]
    
    if not stocks:
        return {"success": False, "message": f"No {direction} found for {timeframe}"}
    
    # Format for display
    currency = '₹' if market == 'India' else '$'
    table = []
    found_tickers = []
    
    for s in stocks:
        found_tickers.append(s['full_ticker'])
        
        # Color code performance
        def fmt_perf(val):
            if val is None:
                return "N/A"
            color = "🟢" if val >= 0 else "🔴"
            return f"{color} {val:+.1f}%"
        
        table.append({
            "Ticker": s['ticker'],
            "Price": s['price_fmt'],
            "Today": fmt_perf(s['change_today']),
            "1W": fmt_perf(s['perf_1w']),
            "1M": fmt_perf(s['perf_1m']),
            "YTD": fmt_perf(s['perf_ytd']),
        })
    
    st.session_state.charts_to_display = found_tickers[:3]
    
    # Get market news
    market_news = get_market_news(market, limit=5)
    news_summary = format_news_for_ai(market_news)
    
    timeframe_names = {
        '1w': 'Week', '1m': 'Month', '3m': '3 Months', 
        '6m': '6 Months', 'ytd': 'YTD', '1y': 'Year'
    }
    
    return {
        "success": True,
        "screen_type": f"Top {direction.title()} ({timeframe_names.get(timeframe, timeframe)})",
        "timeframe": timeframe,
        "found": len(table),
        "table": table,
        "stocks_data": stocks,  # Full data for AI
        "market_news": news_summary
    }

def find_breakout_stocks():
    """Find stocks breaking out - near 52-week highs with volume"""
    market = st.session_state.get('market', 'US')
    stocks_to_scan = ALL_US_STOCKS[:80] if market == 'US' else ALL_INDIA_STOCKS[:50]
    
    results = []
    progress = st.progress(0)
    
    for i, ticker in enumerate(stocks_to_scan):
        progress.progress((i + 1) / len(stocks_to_scan))
        
        try:
            data = get_live_stock_data(ticker)
            if not data or not data['52w_high']:
                continue
            
            # Check if near 52-week high (within 5%)
            pct_from_high = data.get('from_52w_high', -100)
            if pct_from_high is None or pct_from_high < -5:
                continue
            
            # Get technicals for volume check
            technicals = get_advanced_technicals(ticker)
            if not technicals:
                continue
            
            vol_ratio = technicals.get('volume_ratio', 0)
            
            # Want stocks with above average volume
            if vol_ratio < 1.0:
                continue
            
            currency = '₹' if data['market'] == 'India' else '$'
            results.append({
                'ticker': data['display_ticker'],
                'full_ticker': ticker,
                'price': f"{currency}{data['price']:,.2f}",
                'from_high': f"{pct_from_high:+.1f}%",
                'volume': f"{vol_ratio:.1f}x",
                'rsi': technicals.get('rsi', 0),
                'sector': data['sector'][:15] if data['sector'] else 'N/A',
            })
        except:
            continue
    
    progress.empty()
    
    # Sort by closest to 52-week high
    results.sort(key=lambda x: float(x['from_high'].replace('%', '').replace('+', '')), reverse=True)
    
    if not results:
        return {"success": False, "message": "No breakout stocks found"}
    
    st.session_state.charts_to_display = [r['full_ticker'] for r in results[:3]]
    
    # Get market news
    market_news = get_market_news(market, limit=5)
    
    table = [{
        "Ticker": r['ticker'],
        "Price": r['price'],
        "From 52W High": r['from_high'],
        "Volume": r['volume'],
        "RSI": f"{r['rsi']:.0f}" if r['rsi'] else "N/A",
        "Sector": r['sector']
    } for r in results[:15]]
    
    return {
        "success": True,
        "screen_type": "Breakout Stocks (Near 52-Week Highs)",
        "found": len(table),
        "table": table,
        "market_news": format_news_for_ai(market_news)
    }

def find_oversold_bounces():
    """Find oversold stocks that could bounce"""
    market = st.session_state.get('market', 'US')
    stocks_to_scan = ALL_US_STOCKS[:80] if market == 'US' else ALL_INDIA_STOCKS[:50]
    
    results = []
    progress = st.progress(0)
    
    for i, ticker in enumerate(stocks_to_scan):
        progress.progress((i + 1) / len(stocks_to_scan))
        
        try:
            technicals = get_advanced_technicals(ticker)
            if not technicals:
                continue
            
            rsi = technicals.get('rsi', 50)
            bb_pos = technicals.get('bb_position', 0.5)
            
            # Looking for oversold conditions
            if rsi > 35 or bb_pos > 0.3:
                continue
            
            data = get_live_stock_data(ticker)
            if not data:
                continue
            
            # Check it's not a total disaster (some fundamentals)
            if data['pe_ratio'] and data['pe_ratio'] < 0:
                continue
            
            currency = '₹' if data['market'] == 'India' else '$'
            results.append({
                'ticker': data['display_ticker'],
                'full_ticker': ticker,
                'price': f"{currency}{data['price']:,.2f}",
                'rsi': rsi,
                'bb_position': bb_pos * 100,
                'from_high': data.get('from_52w_high', 0),
                'sector': data['sector'][:15] if data['sector'] else 'N/A',
                'pe': data['pe_ratio'],
            })
        except:
            continue
    
    progress.empty()
    
    # Sort by most oversold (lowest RSI)
    results.sort(key=lambda x: x['rsi'])
    
    if not results:
        return {"success": False, "message": "No oversold stocks found"}
    
    st.session_state.charts_to_display = [r['full_ticker'] for r in results[:3]]
    
    market_news = get_market_news(market, limit=5)
    
    table = [{
        "Ticker": r['ticker'],
        "Price": r['price'],
        "RSI": f"🔴 {r['rsi']:.0f}",
        "BB Position": f"{r['bb_position']:.0f}%",
        "From High": f"{r['from_high']}%" if r['from_high'] else "N/A",
        "Sector": r['sector']
    } for r in results[:15]]
    
    return {
        "success": True,
        "screen_type": "Oversold Bounce Candidates",
        "found": len(table),
        "table": table,
        "market_news": format_news_for_ai(market_news)
    }

st.set_page_config(
    page_title="Paula - AI Stock Analyst",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Force dark theme via config
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

# CSS - Modern Full-Width Design
st.markdown("""
<style>
    /* Full width layout */
    .stApp { 
        background: #09090b !important; 
    }
    
    .block-container {
        padding: 2rem 3rem !important;
        max-width: 100% !important;
    }
    
    #MainMenu, footer, header {visibility: hidden;}
    
    /* Typography */
    h1, h2, h3 {
        color: #fafafa !important; 
        font-weight: 600 !important;
    }
    
    h1 { font-size: 2rem !important; }
    h4 { color: #a1a1aa !important; font-weight: 500 !important; }
    
    p, span, div, label {
        color: #a1a1aa !important;
    }
    
    /* Chat messages */
    .stChatMessage {
        background: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        max-width: 100% !important;
    }
    
    .stChatMessage p, .stChatMessage span, .stChatMessage div {
        color: #e4e4e7 !important;
    }
    
    /* Cards/containers */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        background: transparent !important;
    }
    
    /* Selectbox */
    .stSelectbox > div > div {
        background: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 8px !important;
        color: #fafafa !important;
    }
    
    .stSelectbox [data-baseweb="select"] > div {
        background: #18181b !important;
        border-color: #27272a !important;
    }
    
    /* Buttons */
    .stButton > button {
        background: #18181b !important;
        color: #fafafa !important; 
        border: 1px solid #27272a !important; 
        border-radius: 8px !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        background: #27272a !important;
        border-color: #3f3f46 !important;
    }
    
    hr {
        border-color: #27272a !important;
        margin: 1.5rem 0 !important;
    }
    
    /* Header */
    .main-header {
        padding: 1rem 0 0.5rem 0;
        border-bottom: 1px solid #27272a;
        margin-bottom: 1.5rem;
    }
    
    .main-header h1 {
        font-size: 1.5rem !important;
        color: #fafafa !important;
        margin-bottom: 0 !important;
        display: inline-block;
    }
    
    .main-header p {
        color: #52525b !important;
        font-size: 0.85rem !important;
        margin-top: 0.25rem !important;
    }
    
    /* Market badge */
    .market-badge {
        display: inline-flex; 
        align-items: center; 
        gap: 6px;
        background: #18181b;
        padding: 8px 14px; 
        border-radius: 6px; 
        font-size: 13px; 
        color: #a1a1aa !important;
        border: 1px solid #27272a;
    }
    
    /* Text input */
    .stTextInput > div > div > input {
        background: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 8px !important;
        padding: 14px 16px !important;
        color: #fafafa !important;
        font-size: 15px !important;
    }
    
    .stTextInput > div > div > input::placeholder {
        color: #52525b !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #3f3f46 !important;
        box-shadow: 0 0 0 2px rgba(63, 63, 70, 0.3) !important;
        background: #18181b !important;
    }
    
    /* Form */
    [data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    
    /* Dataframe */
    .stDataFrame { 
        background: #18181b !important; 
        border-radius: 8px !important;
        border: 1px solid #27272a !important;
    }
    
    [data-testid="stDataFrame"] {
        background: #18181b !important;
    }
    
    /* Progress bar */
    .stProgress > div > div { 
        background: linear-gradient(90deg, #3f3f46, #52525b) !important; 
    }
    
    /* Warning/info */
    .stWarning {
        background: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 8px !important;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: #3f3f46 !important;
    }
    
    /* Plotly chart background */
    .js-plotly-plot {
        background: transparent !important;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #09090b; }
    ::-webkit-scrollbar-thumb { background: #27272a; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #3f3f46; }
    
    /* Columns spacing */
    [data-testid="column"] {
        padding: 0 0.5rem !important;
    }
    
    /* Welcome section */
    .welcome-text {
        color: #71717a !important;
        font-size: 1.1rem !important;
        margin-bottom: 1rem !important;
    }
    
    /* Fix microphone recorder styling */
    .stAudioInput, [data-testid="stAudioInput"] {
        background: transparent !important;
        border: none !important;
    }
    
    iframe[title="streamlit_mic_recorder.speech_to_text"] {
        border: none !important;
        background: transparent !important;
    }
    
    /* Settings expander */
    .streamlit-expanderHeader {
        background: #18181b !important;
        border: 1px solid #27272a !important;
        border-radius: 8px !important;
        color: #a1a1aa !important;
    }
    
    .streamlit-expanderContent {
        background: #18181b !important;
        border: 1px solid #27272a !important;
        border-top: none !important;
    }
    
    /* Toggle switch */
    .stCheckbox {
        color: #a1a1aa !important;
    }
    
    .stCheckbox > label > span {
        color: #e4e4e7 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==================== STOCK DATA ====================
US_STOCKS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'V', 'UNH',
    'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'XOM', 'HD', 'CVX', 'MRK', 'ABBV',
    'PEP', 'KO', 'AVGO', 'COST', 'LLY', 'TMO', 'ACN', 'MCD', 'CSCO', 'ABT',
    'DHR', 'CRM', 'VZ', 'ADBE', 'NKE', 'NEE', 'WFC', 'TXN', 'PM', 'UPS',
    'RTX', 'HON', 'ORCL', 'BMY', 'QCOM', 'UNP', 'INTU', 'LOW', 'AMD', 'COP']

# NASDAQ 100 stocks
NASDAQ_100 = [
    'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'GOOG', 'TSLA', 'AVGO', 'COST',
    'PEP', 'ADBE', 'CSCO', 'NFLX', 'CMCSA', 'AMD', 'TMUS', 'INTC', 'INTU', 'QCOM',
    'TXN', 'AMGN', 'AMAT', 'ISRG', 'HON', 'BKNG', 'SBUX', 'MDLZ', 'VRTX', 'GILD',
    'ADI', 'ADP', 'REGN', 'LRCX', 'PANW', 'MU', 'KLAC', 'SNPS', 'CDNS', 'ASML',
    'PYPL', 'MELI', 'CRWD', 'ORLY', 'MAR', 'MNST', 'CTAS', 'NXPI', 'MRVL', 'ADSK',
    'FTNT', 'ABNB', 'PCAR', 'WDAY', 'CHTR', 'KDP', 'AEP', 'PAYX', 'CPRT', 'ROST',
    'KHC', 'MCHP', 'ODFL', 'EXC', 'DXCM', 'LULU', 'EA', 'VRSK', 'IDXX', 'FAST',
    'CTSH', 'XEL', 'GEHC', 'CSGP', 'BKR', 'FANG', 'TEAM', 'ANSS', 'ZS', 'DDOG',
    'ILMN', 'WBD', 'ALGN', 'EBAY', 'BIIB', 'ENPH', 'SIRI', 'JD', 'ZM', 'LCID',
    'RIVN', 'CEG', 'TTWO', 'WBA', 'DLTR', 'SGEN', 'MRNA', 'AZN', 'PDD', 'SPLK'
]

# S&P 500 top 100 by market cap (simplified)
SP500_TOP = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'V', 'UNH',
    'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'XOM', 'HD', 'CVX', 'MRK', 'ABBV',
    'PEP', 'KO', 'AVGO', 'COST', 'LLY', 'TMO', 'ACN', 'MCD', 'CSCO', 'ABT',
    'DHR', 'CRM', 'VZ', 'ADBE', 'NKE', 'NEE', 'WFC', 'TXN', 'PM', 'UPS',
    'RTX', 'HON', 'ORCL', 'BMY', 'QCOM', 'UNP', 'INTU', 'LOW', 'AMD', 'COP',
    'SPGI', 'CAT', 'BA', 'GE', 'AMGN', 'IBM', 'SBUX', 'GS', 'BLK', 'GILD',
    'MDT', 'CVS', 'AXP', 'ISRG', 'DE', 'NOW', 'BKNG', 'ADI', 'MDLZ', 'TJX',
    'SYK', 'MMC', 'VRTX', 'REGN', 'PLD', 'LMT', 'CB', 'ZTS', 'MO', 'CI',
    'TMUS', 'SO', 'DUK', 'CL', 'CME', 'BDX', 'EOG', 'SLB', 'EQIX', 'NOC',
    'ITW', 'AON', 'CSX', 'BSX', 'FI', 'APD', 'ICE', 'WM', 'MPC', 'PNC'
]

INDIAN_STOCKS = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'HCLTECH.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS',
    'SUNPHARMA.NS', 'TITAN.NS', 'BAJFINANCE.NS', 'DMART.NS', 'WIPRO.NS',
    'NTPC.NS', 'POWERGRID.NS', 'ONGC.NS', 'TATAMOTORS.NS', 'ADANIENT.NS',
    'ADANIPORTS.NS', 'COALINDIA.NS', 'JSWSTEEL.NS', 'TATASTEEL.NS', 'HINDALCO.NS']

# NIFTY 50
NIFTY_50 = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'HCLTECH.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS',
    'SUNPHARMA.NS', 'TITAN.NS', 'BAJFINANCE.NS', 'WIPRO.NS', 'NTPC.NS',
    'POWERGRID.NS', 'ONGC.NS', 'TATAMOTORS.NS', 'ADANIENT.NS', 'ADANIPORTS.NS',
    'COALINDIA.NS', 'JSWSTEEL.NS', 'TATASTEEL.NS', 'HINDALCO.NS', 'M&M.NS',
    'BAJAJ-AUTO.NS', 'ULTRACEMCO.NS', 'NESTLEIND.NS', 'TECHM.NS', 'DIVISLAB.NS',
    'DRREDDY.NS', 'CIPLA.NS', 'GRASIM.NS', 'APOLLOHOSP.NS', 'EICHERMOT.NS',
    'HEROMOTOCO.NS', 'TATACONSUM.NS', 'BPCL.NS', 'BRITANNIA.NS', 'INDUSINDBK.NS',
    'SBILIFE.NS', 'HDFCLIFE.NS', 'UPL.NS', 'BAJAJFINSV.NS', 'SHREECEM.NS'
]

# Hot/Trending stocks outside main indices (small/mid caps, meme stocks, AI plays, etc.)
TRENDING_US = [
    # AI & Tech plays
    'PLTR', 'SMCI', 'ARM', 'IONQ', 'RGTI', 'QUBT', 'SOUN', 'BBAI', 'AI', 'PATH',
    # Semiconductor
    'MRVL', 'ON', 'MPWR', 'LSCC', 'WOLF', 'ACLS', 'CRUS', 'RMBS', 'SWKS', 'QRVO',
    # EV & Clean Energy
    'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'FSR', 'CHPT', 'BLNK', 'QS', 'PLUG',
    'FCEL', 'BE', 'ENPH', 'SEDG', 'RUN', 'NOVA', 'ARRY',
    # Biotech/Pharma
    'MRNA', 'BNTX', 'CRSP', 'EDIT', 'NTLA', 'BEAM', 'VERV', 'RXRX', 'DNA',
    # Fintech & Crypto-related
    'SQ', 'AFRM', 'UPST', 'SOFI', 'NU', 'MSTR', 'COIN', 'HOOD', 'RIOT', 'MARA',
    # Growth/Momentum
    'DUOL', 'RKLB', 'ASTS', 'LUNR', 'RDW', 'AEHR', 'CELH', 'HIMS', 'TMDX',
    # Meme/Retail favorites
    'GME', 'AMC', 'BBBY', 'BB', 'WISH', 'CLOV', 'SPCE', 'OPEN',
    # Other popular
    'NET', 'DDOG', 'CRWD', 'ZS', 'OKTA', 'MDB', 'SNOW', 'U', 'RBLX', 'TTWO',
    'SE', 'SHOP', 'SQ', 'ROKU', 'PINS', 'SNAP', 'TWLO', 'DOCU', 'ZM'
]

# Small/Mid cap Indian stocks
TRENDING_INDIA = [
    'ZOMATO.NS', 'PAYTM.NS', 'NYKAA.NS', 'POLICYBZR.NS', 'CARTRADE.NS',
    'IRCTC.NS', 'TATAELXSI.NS', 'PERSISTENT.NS', 'COFORGE.NS', 'MPHASIS.NS',
    'LTTS.NS', 'HAPPSTMNDS.NS', 'ROUTE.NS', 'INTELLECT.NS', 'KPITTECH.NS',
    'ANGELONE.NS', 'CDSL.NS', 'BSE.NS', 'MCX.NS', 'CAMS.NS',
    'DELHIVERY.NS', 'MAPMYINDIA.NS', 'LATENTVIEW.NS', 'CAMPUS.NS', 'MEDANTA.NS',
    'RAINBOW.NS', 'METROPOLIS.NS', 'LALPATHLAB.NS', 'SYNGENE.NS', 'AFFLE.NS',
    'NAZARA.NS', 'TANLA.NS', 'RATEGAIN.NS', 'SBICARD.NS', 'MUTHOOTFIN.NS',
    'CHOLAFIN.NS', 'BAJFINANCE.NS', 'ICICIGI.NS', 'HDFCAMC.NS', 'NAM-INDIA.NS',
    'TRENT.NS', 'PAGEIND.NS', 'RELAXO.NS', 'BATAINDIA.NS', 'VBL.NS'
]

# All stocks combined for scanning
ALL_US_STOCKS = list(set(US_STOCKS + NASDAQ_100 + SP500_TOP + TRENDING_US))
ALL_INDIA_STOCKS = list(set(INDIAN_STOCKS + NIFTY_50 + TRENDING_INDIA))

# Company name to ticker mapping (case-insensitive)
COMPANY_TO_TICKER = {
    # US Companies
    'apple': 'AAPL', 'microsoft': 'MSFT', 'google': 'GOOGL', 'alphabet': 'GOOGL',
    'amazon': 'AMZN', 'nvidia': 'NVDA', 'meta': 'META', 'facebook': 'META',
    'tesla': 'TSLA', 'berkshire': 'BRK-B', 'visa': 'V', 'unitedhealth': 'UNH',
    'johnson': 'JNJ', 'walmart': 'WMT', 'jpmorgan': 'JPM', 'chase': 'JPM',
    'mastercard': 'MA', 'procter': 'PG', 'exxon': 'XOM', 'home depot': 'HD',
    'chevron': 'CVX', 'merck': 'MRK', 'abbvie': 'ABBV', 'pepsi': 'PEP',
    'pepsico': 'PEP', 'coca cola': 'KO', 'coke': 'KO', 'broadcom': 'AVGO',
    'costco': 'COST', 'eli lilly': 'LLY', 'lilly': 'LLY', 'thermo fisher': 'TMO',
    'accenture': 'ACN', 'mcdonalds': 'MCD', "mcdonald's": 'MCD', 'cisco': 'CSCO',
    'abbott': 'ABT', 'danaher': 'DHR', 'salesforce': 'CRM', 'verizon': 'VZ',
    'adobe': 'ADBE', 'nike': 'NKE', 'nextera': 'NEE', 'wells fargo': 'WFC',
    'texas instruments': 'TXN', 'philip morris': 'PM', 'ups': 'UPS',
    'raytheon': 'RTX', 'honeywell': 'HON', 'oracle': 'ORCL', 'bristol': 'BMY',
    'qualcomm': 'QCOM', 'union pacific': 'UNP', 'intuit': 'INTU', 'lowes': 'LOW',
    "lowe's": 'LOW', 'amd': 'AMD', 'conocophillips': 'COP', 'netflix': 'NFLX',
    'disney': 'DIS', 'paypal': 'PYPL', 'intel': 'INTC', 'ibm': 'IBM',
    'boeing': 'BA', 'caterpillar': 'CAT', 'goldman': 'GS', 'morgan stanley': 'MS',
    'spotify': 'SPOT', 'uber': 'UBER', 'airbnb': 'ABNB', 'zoom': 'ZM',
    'snowflake': 'SNOW', 'palantir': 'PLTR', 'coinbase': 'COIN', 'robinhood': 'HOOD',
    
    # Indian Companies
    'reliance': 'RELIANCE', 'tcs': 'TCS', 'tata consultancy': 'TCS',
    'hdfc': 'HDFCBANK', 'hdfc bank': 'HDFCBANK', 'infosys': 'INFY',
    'icici': 'ICICIBANK', 'icici bank': 'ICICIBANK', 'hindustan unilever': 'HINDUNILVR',
    'hul': 'HINDUNILVR', 'itc': 'ITC', 'sbi': 'SBIN', 'state bank': 'SBIN',
    'bharti airtel': 'BHARTIARTL', 'airtel': 'BHARTIARTL', 'kotak': 'KOTAKBANK',
    'larsen': 'LT', 'l&t': 'LT', 'hcl': 'HCLTECH', 'axis': 'AXISBANK',
    'axis bank': 'AXISBANK', 'asian paints': 'ASIANPAINT', 'maruti': 'MARUTI',
    'maruti suzuki': 'MARUTI', 'sun pharma': 'SUNPHARMA', 'titan': 'TITAN',
    'bajaj finance': 'BAJFINANCE', 'bajaj': 'BAJFINANCE', 'dmart': 'DMART',
    'avenue supermarts': 'DMART', 'wipro': 'WIPRO'
}

def get_ticker_from_name(query):
    """Convert company name to ticker symbol"""
    query_lower = query.lower().strip()
    
    # Direct match
    if query_lower in COMPANY_TO_TICKER:
        return COMPANY_TO_TICKER[query_lower]
    
    # Partial match (e.g., "apple inc" should match "apple")
    for name, ticker in COMPANY_TO_TICKER.items():
        if name in query_lower or query_lower in name:
            return ticker
    
    return None

def get_stock_list():
    return INDIAN_STOCKS if st.session_state.get('market') == 'India' else US_STOCKS

def get_display_ticker(ticker):
    return ticker.replace('.NS', '').replace('.BO', '')

def get_quick_price(ticker):
    """Get just the price quickly - for simple price queries"""
    try:
        stock = yf.Ticker(ticker)
        
        # Try intraday data first (most accurate for current price)
        try:
            hist = stock.history(period='1d', interval='1m')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
                prev_close = float(hist['Open'].iloc[0])
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                return {
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': round(change_pct, 2),
                    'source': 'realtime'
                }
        except:
            pass
        
        # Fallback to fast_info
        try:
            fast = stock.fast_info
            price = fast.get('lastPrice') or fast.get('regularMarketPrice')
            prev = fast.get('previousClose')
            if price:
                price = float(price)
                prev = float(prev) if prev else price
                change = price - prev
                change_pct = (change / prev * 100) if prev > 0 else 0
                return {
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': round(change_pct, 2),
                    'source': 'fast_info'
                }
        except:
            pass
        
        # Last fallback
        try:
            hist = stock.history(period='5d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])
                prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
                change = price - prev
                change_pct = (change / prev * 100) if prev > 0 else 0
                return {
                    'price': round(price, 2),
                    'change': round(change, 2),
                    'change_pct': round(change_pct, 2),
                    'source': 'history'
                }
        except:
            pass
        
        return None
    except:
        return None

def format_market_cap(value, market='US'):
    if value is None: return "N/A"
    symbol = '₹' if market == 'India' else '$'
    if value >= 1e12: return f"{symbol}{value/1e12:.2f}T"
    elif value >= 1e9: return f"{symbol}{value/1e9:.2f}B"
    elif value >= 1e6: return f"{symbol}{value/1e6:.2f}M"
    return f"{symbol}{value:,.0f}"

# ==================== TECHNICAL ====================
def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data):
    exp1 = data['Close'].ewm(span=12, adjust=False).mean()
    exp2 = data['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal

def create_technical_chart(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty or len(hist) < 30: return None
        
        display_name = get_display_ticker(ticker)
        hist['RSI'] = calculate_rsi(hist)
        hist['MACD'], hist['Signal'], hist['MACD_Hist'] = calculate_macd(hist)
        hist['MA20'] = hist['Close'].rolling(window=20).mean()
        hist['MA50'] = hist['Close'].rolling(window=50).mean()
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            row_heights=[0.5, 0.25, 0.25], subplot_titles=(f'{display_name} Price', 'RSI', 'MACD'))
        
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'],
            low=hist['Low'], close=hist['Close'], name='Price',
            increasing_line_color='#10b981', decreasing_line_color='#ef4444'), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA20'], name='MA20', line=dict(color='#f59e0b', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA50'], name='MA50', line=dict(color='#8b5cf6', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI', line=dict(color='#06b6d4')), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], name='MACD', line=dict(color='#3b82f6')), row=3, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal'], name='Signal', line=dict(color='#f59e0b')), row=3, col=1)
        
        fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            height=600, margin=dict(l=50, r=30, t=40, b=30), showlegend=True, xaxis_rangeslider_visible=False)
        return fig
    except: return None

# ==================== DATA ====================
def get_live_stock_data(ticker):
    """Get fresh stock data - prioritize real-time price accuracy"""
    try:
        stock = yf.Ticker(ticker)
        
        current_price = None
        prev_close = None
        market_cap = None
        fifty_two_week_high = None
        fifty_two_week_low = None
        
        # Method 1: Get latest price from intraday history (MOST ACCURATE)
        try:
            hist_1d = stock.history(period='1d', interval='1m')
            if not hist_1d.empty:
                current_price = float(hist_1d['Close'].iloc[-1])
        except:
            pass
        
        # Method 2: Try fast_info
        if current_price is None:
            try:
                fast = stock.fast_info
                current_price = fast.get('lastPrice') or fast.get('regularMarketPrice')
                if current_price:
                    current_price = float(current_price)
                prev_close = fast.get('previousClose')
                market_cap = fast.get('marketCap')
                fifty_two_week_high = fast.get('yearHigh')
                fifty_two_week_low = fast.get('yearLow')
            except:
                pass
        
        # Method 3: Get from info dict
        info = {}
        try:
            info = stock.info or {}
        except:
            pass
        
        if current_price is None:
            current_price = info.get('regularMarketPrice') or info.get('currentPrice')
            if current_price:
                current_price = float(current_price)
        
        # Method 4: Try 5-day history
        if current_price is None:
            try:
                hist_5d = stock.history(period='5d')
                if not hist_5d.empty:
                    current_price = float(hist_5d['Close'].iloc[-1])
            except:
                pass
        
        if current_price is None:
            return None
        
        # Get previous close
        if prev_close is None:
            prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
        
        if prev_close is None:
            try:
                hist_5d = stock.history(period='5d')
                if len(hist_5d) >= 2:
                    prev_close = float(hist_5d['Close'].iloc[-2])
            except:
                prev_close = current_price
        
        if prev_close:
            prev_close = float(prev_close)
        else:
            prev_close = current_price
        
        # Get other data
        if market_cap is None:
            market_cap = info.get('marketCap')
        if fifty_two_week_high is None:
            fifty_two_week_high = info.get('fiftyTwoWeekHigh')
        if fifty_two_week_low is None:
            fifty_two_week_low = info.get('fiftyTwoWeekLow')
        
        market = 'India' if '.NS' in ticker or '.BO' in ticker else 'US'
        change = current_price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close and prev_close > 0 else 0
        
        # Calculate additional metrics
        from_52w_high = ((current_price - fifty_two_week_high) / fifty_two_week_high * 100) if fifty_two_week_high and fifty_two_week_high > 0 else None
        from_52w_low = ((current_price - fifty_two_week_low) / fifty_two_week_low * 100) if fifty_two_week_low and fifty_two_week_low > 0 else None
        
        return {
            "ticker": ticker, "display_ticker": get_display_ticker(ticker),
            "name": info.get('longName') or info.get('shortName') or get_display_ticker(ticker),
            "price": round(float(current_price), 2), 
            "change": round(float(change), 2), 
            "change_pct": round(float(change_pct), 2),
            "market_cap": market_cap, 
            "market_cap_fmt": format_market_cap(market_cap, market),
            "pe_ratio": info.get('trailingPE'), 
            "forward_pe": info.get('forwardPE'),
            "peg_ratio": info.get('pegRatio'),
            "roe": info.get('returnOnEquity'),
            "profit_margin": info.get('profitMargins'), 
            "revenue_growth": info.get('revenueGrowth'),
            "earnings_growth": info.get('earningsGrowth'),
            "debt_to_equity": info.get('debtToEquity'),
            "current_ratio": info.get('currentRatio'), 
            "dividend_yield": info.get('dividendYield'),
            "beta": info.get('beta'),
            "52w_high": fifty_two_week_high,
            "52w_low": fifty_two_week_low,
            "from_52w_high": round(from_52w_high, 1) if from_52w_high else None,
            "from_52w_low": round(from_52w_low, 1) if from_52w_low else None,
            "avg_volume": info.get('averageVolume'),
            "target_price": info.get('targetMeanPrice'),
            "target_high": info.get('targetHighPrice'),
            "target_low": info.get('targetLowPrice'),
            "recommendation": info.get('recommendationKey'),
            "num_analysts": info.get('numberOfAnalystOpinions'),
            "sector": info.get('sector', 'N/A'), 
            "industry": info.get('industry', 'N/A'), 
            "market": market,
        }
    except Exception as e:
        return None

# ==================== ANALYSIS ====================
def validate_ticker(ticker):
    """Validate ticker symbol format"""
    if not ticker or not isinstance(ticker, str):
        return False
    # Remove suffix for validation
    clean = ticker.upper().strip().replace('.NS', '').replace('.BO', '')
    # Valid ticker: 1-10 alphanumeric chars, may include hyphen
    if not clean or len(clean) > 10:
        return False
    if not re.match(r'^[A-Z0-9\-]+$', clean):
        return False
    return True

def analyze_stock(ticker, show_chart=None):
    # Use settings if not explicitly specified
    if show_chart is None:
        show_chart = st.session_state.get('show_charts', True)
    
    # Validate input
    if not validate_ticker(ticker):
        return {"success": False, "error": f"Invalid ticker symbol: {ticker}", "ticker": ticker}
    
    original = ticker.upper().strip().replace('.NS', '').replace('.BO', '')
    market = st.session_state.get('market', 'US')
    full_ticker = f"{original}.NS" if market == 'India' else original
    data = get_live_stock_data(full_ticker)
    
    if not data:
        alt_ticker = original if market == 'India' else f"{original}.NS"
        data = get_live_stock_data(alt_ticker)
        full_ticker = alt_ticker
    
    if not data: 
        return {"success": False, "error": f"Could not fetch data for {original}. The stock may be delisted or the symbol is incorrect.", "ticker": original}
    
    # Auto-show chart based on settings
    if show_chart:
        st.session_state.charts_to_display = [full_ticker]
    
    # Get advanced technicals
    technicals = get_advanced_technicals(full_ticker)
    
    # Get earnings data
    earnings = get_earnings_data(full_ticker)
    
    # Get news and sentiment
    news = get_stock_news(full_ticker, limit=8)
    news_summary = format_news_for_ai(news)
    news_sentiment = analyze_news_sentiment(news)
    
    # Calculate comprehensive trading score
    trading_analysis = calculate_trading_score(data, technicals, earnings, news_sentiment)
    
    currency = '₹' if data['market'] == 'India' else '$'
    
    # Build comprehensive response
    result = {
        "success": True, 
        "ticker": data['display_ticker'], 
        "name": data['name'],
        "sector": data['sector'],
        "industry": data['industry'],
        "price": f"{currency}{data['price']:,.2f}",
        "change_today": f"{data['change']:+.2f} ({data['change_pct']:+.2f}%)",
        "market_cap": data['market_cap_fmt'],
        
        # Trading Rating (the main score)
        "trading_rating": trading_analysis['rating'],
        "trading_score": f"{trading_analysis['score']}/{trading_analysis['max_score']} ({trading_analysis['percentage']:.0f}%)",
        "trading_action": trading_analysis['action'],
        "buy_signals": trading_analysis['signals'],
        "warnings": trading_analysis['warnings'],
        
        # Valuation
        "pe_ratio": round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A",
        "forward_pe": round(data['forward_pe'], 2) if data['forward_pe'] else "N/A",
        "peg_ratio": round(data['peg_ratio'], 2) if data['peg_ratio'] else "N/A",
        
        # Performance
        "roe": f"{data['roe']*100:.1f}%" if data['roe'] else "N/A",
        "profit_margin": f"{data['profit_margin']*100:.1f}%" if data['profit_margin'] else "N/A",
        "revenue_growth": f"{data['revenue_growth']*100:.1f}%" if data['revenue_growth'] else "N/A",
        "earnings_growth": f"{data['earnings_growth']*100:.1f}%" if data['earnings_growth'] else "N/A",
        
        # 52-Week Range
        "52_week_high": f"{currency}{data['52w_high']:,.2f}" if data['52w_high'] else "N/A",
        "52_week_low": f"{currency}{data['52w_low']:,.2f}" if data['52w_low'] else "N/A",
        "from_52w_high": f"{data['from_52w_high']}%" if data['from_52w_high'] else "N/A",
        "beta": round(data['beta'], 2) if data['beta'] else "N/A",
        
        # Analyst
        "analyst_rating": data['recommendation'].replace('_', ' ').title() if data['recommendation'] else "N/A",
        "num_analysts": data['num_analysts'] if data['num_analysts'] else "N/A",
        "target_price": f"{currency}{data['target_price']:,.2f}" if data['target_price'] else "N/A",
        "target_high": f"{currency}{data['target_high']:,.2f}" if data['target_high'] else "N/A",
        "target_low": f"{currency}{data['target_low']:,.2f}" if data['target_low'] else "N/A",
        
        # News
        "news": news_summary,
        "news_sentiment": "Positive" if news_sentiment > 0.2 else ("Negative" if news_sentiment < -0.2 else "Neutral"),
    }
    
    # Add technicals if available
    if technicals:
        result["technicals"] = {
            "rsi": round(technicals['rsi'], 1) if technicals.get('rsi') else "N/A",
            "macd_signal": technicals.get('macd_crossover', 'none'),
            "ema_signal": technicals.get('ema_crossover', 'none'),
            "price_vs_sma20": f"{technicals['price_vs_sma20']:+.1f}%" if technicals.get('price_vs_sma20') else "N/A",
            "price_vs_sma50": f"{technicals['price_vs_sma50']:+.1f}%" if technicals.get('price_vs_sma50') else "N/A",
            "bollinger_position": f"{technicals['bb_position']*100:.0f}%" if technicals.get('bb_position') else "N/A",
            "volume_ratio": f"{technicals['volume_ratio']:.1f}x avg" if technicals.get('volume_ratio') else "N/A",
            "atr_volatility": f"{technicals['atr_percent']:.1f}%" if technicals.get('atr_percent') else "N/A",
            "momentum_5d": f"{technicals['roc_5']:+.1f}%" if technicals.get('roc_5') else "N/A",
            "momentum_20d": f"{technicals['roc_20']:+.1f}%" if technicals.get('roc_20') else "N/A",
        }
    
    # Add earnings data if available
    if earnings:
        result["earnings"] = {
            "next_earnings_date": earnings.get('next_earnings', 'N/A'),
            "recent_quarters": earnings.get('recent_earnings', []),
        }
    
    # Calculate upside to target
    if data['target_price'] and data['price']:
        upside = ((data['target_price'] - data['price']) / data['price']) * 100
        result['upside_to_target'] = f"{upside:+.1f}%"
    
    return result

def compare_stocks(tickers_str):
    tickers = [t.strip().upper().replace('.NS', '') for t in re.split(r'[,\s]+', tickers_str) if t.strip()]
    results, full_tickers = [], []
    market = st.session_state.get('market', 'US')
    
    for ticker in tickers[:5]:
        full_ticker = f"{ticker}.NS" if market == 'India' else ticker
        data = get_live_stock_data(full_ticker)
        if not data:
            data = get_live_stock_data(ticker if market == 'India' else f"{ticker}.NS")
            full_ticker = ticker if market == 'India' else f"{ticker}.NS"
        if data:
            full_tickers.append(full_ticker)
            currency = '₹' if data['market'] == 'India' else '$'
            results.append({
                "Ticker": data['display_ticker'], "Price": f"{currency}{data['price']:,.2f}",
                "Change": f"{'🟢' if data['change_pct'] >= 0 else '🔴'} {data['change_pct']:+.2f}%",
                "P/E": round(data['pe_ratio'], 1) if data['pe_ratio'] else "N/A",
                "Sector": data['sector'][:15] if data['sector'] else "N/A"
            })
    
    st.session_state.charts_to_display = full_tickers
    return {"success": True, "count": len(results), "table": results}

def screen_stocks(screen_type):
    results, found_tickers = [], []
    stocks = get_stock_list()
    market = st.session_state.get('market', 'US')
    
    progress = st.progress(0)
    for i, ticker in enumerate(stocks):
        progress.progress((i + 1) / len(stocks))
        data = get_live_stock_data(ticker)
        if not data: continue
        
        currency = '₹' if data['market'] == 'India' else '$'
        
        if screen_type == "undervalued" and data['pe_ratio'] and 0 < data['pe_ratio'] < 20 and data['roe'] and data['roe'] > 0.12:
            found_tickers.append(ticker)
            results.append({"Ticker": data['display_ticker'], "Price": f"{currency}{data['price']:,.2f}",
                          "P/E": round(data['pe_ratio'], 1), "ROE": f"{data['roe']*100:.0f}%"})
        elif screen_type == "growth" and data['roe'] and data['roe'] > 0.15 and data['profit_margin'] and data['profit_margin'] > 0.10:
            found_tickers.append(ticker)
            results.append({"Ticker": data['display_ticker'], "Price": f"{currency}{data['price']:,.2f}",
                          "ROE": f"{data['roe']*100:.0f}%", "Margin": f"{data['profit_margin']*100:.0f}%"})
        elif screen_type == "dividend" and data['dividend_yield'] and data['dividend_yield'] > 0.02:
            found_tickers.append(ticker)
            results.append({"Ticker": data['display_ticker'], "Price": f"{currency}{data['price']:,.2f}",
                          "Yield": f"{data['dividend_yield']*100:.2f}%"})
    
    progress.empty()
    st.session_state.charts_to_display = found_tickers[:3]
    
    # Get market news for context
    market_news = get_market_news(market, limit=5)
    news_summary = format_news_for_ai(market_news)
    
    if results: 
        return {
            "success": True, 
            "screen_type": screen_type.title(), 
            "found": len(results), 
            "table": results[:15],
            "market_news": news_summary
        }
    return {"success": False, "message": f"No {screen_type} stocks found"}

def screen_by_strategy(strategy, stock_list=None):
    """Screen stocks using various investment strategies"""
    market = st.session_state.get('market', 'US')
    
    # Determine which list to use
    if stock_list is None:
        stock_list = NASDAQ_100 if market == 'US' else NIFTY_50
    
    results = []
    found_tickers = []
    
    progress = st.progress(0)
    stock_data_list = []
    
    # First pass: collect all data
    for i, ticker in enumerate(stock_list[:50]):  # Limit to 50 for speed
        progress.progress((i + 1) / min(len(stock_list), 50))
        data = get_live_stock_data(ticker)
        if data:
            stock_data_list.append(data)
    
    progress.empty()
    
    currency = '₹' if market == 'India' else '$'
    
    if strategy == "momentum":
        # Best performers (highest % change)
        sorted_stocks = sorted(stock_data_list, key=lambda x: x['change_pct'] or 0, reverse=True)
        for data in sorted_stocks[:15]:
            if data['change_pct'] and data['change_pct'] > 0:
                found_tickers.append(data['ticker'])
                results.append({
                    "Ticker": data['display_ticker'],
                    "Price": f"{currency}{data['price']:,.2f}",
                    "Change": f"+{data['change_pct']:.2f}%",
                    "Sector": data['sector'][:12] if data['sector'] else "N/A"
                })
    
    elif strategy == "value":
        # Low P/E with good ROE (Warren Buffett style)
        value_stocks = [d for d in stock_data_list if d['pe_ratio'] and 0 < d['pe_ratio'] < 20 and d['roe'] and d['roe'] > 0.10]
        sorted_stocks = sorted(value_stocks, key=lambda x: x['pe_ratio'])
        for data in sorted_stocks[:15]:
            found_tickers.append(data['ticker'])
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "P/E": round(data['pe_ratio'], 1),
                "ROE": f"{data['roe']*100:.0f}%"
            })
    
    elif strategy == "quality":
        # High ROE, good margins, low debt (quality companies)
        quality_stocks = [d for d in stock_data_list if d['roe'] and d['roe'] > 0.15 and d['profit_margin'] and d['profit_margin'] > 0.10]
        sorted_stocks = sorted(quality_stocks, key=lambda x: x['roe'] or 0, reverse=True)
        for data in sorted_stocks[:15]:
            found_tickers.append(data['ticker'])
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "ROE": f"{data['roe']*100:.0f}%",
                "Margin": f"{data['profit_margin']*100:.0f}%"
            })
    
    elif strategy == "dividend":
        # High dividend yield
        div_stocks = [d for d in stock_data_list if d['dividend_yield'] and d['dividend_yield'] > 0.02]
        sorted_stocks = sorted(div_stocks, key=lambda x: x['dividend_yield'] or 0, reverse=True)
        for data in sorted_stocks[:15]:
            found_tickers.append(data['ticker'])
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "Yield": f"{data['dividend_yield']*100:.2f}%",
                "Sector": data['sector'][:12] if data['sector'] else "N/A"
            })
    
    elif strategy == "large_cap":
        # Largest by market cap
        cap_stocks = [d for d in stock_data_list if d['market_cap']]
        sorted_stocks = sorted(cap_stocks, key=lambda x: x['market_cap'] or 0, reverse=True)
        for data in sorted_stocks[:15]:
            found_tickers.append(data['ticker'])
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "Market Cap": data['market_cap_fmt'],
                "Change": f"{data['change_pct']:+.2f}%"
            })
    
    elif strategy == "low_pe":
        # Lowest P/E ratios
        pe_stocks = [d for d in stock_data_list if d['pe_ratio'] and d['pe_ratio'] > 0]
        sorted_stocks = sorted(pe_stocks, key=lambda x: x['pe_ratio'])
        for data in sorted_stocks[:15]:
            found_tickers.append(data['ticker'])
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "P/E": round(data['pe_ratio'], 1),
                "Sector": data['sector'][:12] if data['sector'] else "N/A"
            })
    
    elif strategy == "top_gainers":
        # Today's top gainers
        sorted_stocks = sorted(stock_data_list, key=lambda x: x['change_pct'] or 0, reverse=True)
        for data in sorted_stocks[:15]:
            found_tickers.append(data['ticker'])
            color = "🟢" if data['change_pct'] >= 0 else "🔴"
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "Change": f"{color} {data['change_pct']:+.2f}%",
                "Sector": data['sector'][:12] if data['sector'] else "N/A"
            })
    
    elif strategy == "top_losers":
        # Today's top losers
        sorted_stocks = sorted(stock_data_list, key=lambda x: x['change_pct'] or 0)
        for data in sorted_stocks[:15]:
            found_tickers.append(data['ticker'])
            color = "🟢" if data['change_pct'] >= 0 else "🔴"
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "Change": f"{color} {data['change_pct']:+.2f}%",
                "Sector": data['sector'][:12] if data['sector'] else "N/A"
            })
    
    else:
        # Default: show all with basic info
        for data in stock_data_list[:15]:
            found_tickers.append(data['ticker'])
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "Change": f"{data['change_pct']:+.2f}%",
                "P/E": round(data['pe_ratio'], 1) if data['pe_ratio'] else "N/A"
            })
    
    st.session_state.charts_to_display = found_tickers[:3]
    
    strategy_names = {
        "momentum": "Momentum (Top Performers)",
        "value": "Value Investing (Low P/E, High ROE)",
        "quality": "Quality (High ROE & Margins)",
        "dividend": "Dividend Income",
        "large_cap": "Largest Companies",
        "low_pe": "Lowest P/E Ratios",
        "top_gainers": "Today's Top Gainers",
        "top_losers": "Today's Top Losers"
    }
    
    # Get market news for context
    market_news = get_market_news(market, limit=5)
    news_summary = format_news_for_ai(market_news)
    
    if results:
        return {
            "success": True, 
            "strategy": strategy_names.get(strategy, strategy.title()),
            "found": len(results), 
            "table": results,
            "market_news": news_summary
        }
    return {"success": False, "message": f"No stocks found for {strategy} strategy"}

# ==================== AI ====================
def detect_and_execute(message):
    msg = message.lower().strip()
    
    # Clear charts for new queries
    st.session_state.charts_to_display = []
    
    # Check if user explicitly wants/doesn't want a chart
    no_chart = any(w in msg for w in ['no chart', 'no graph', 'without chart', 'without graph', 'just data', 'data only'])
    want_chart = any(w in msg for w in ['show chart', 'show graph', 'with chart', 'with graph'])
    
    # Determine if we should show chart
    if no_chart:
        show_chart = False
    elif want_chart:
        show_chart = True
    else:
        show_chart = st.session_state.get('show_charts', True)
    
    # Handle greetings and casual conversation - don't trigger stock analysis
    greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 
                 'howdy', 'sup', 'what\'s up', 'whats up', 'yo', 'hola', 'greetings',
                 'how are you', 'how r u', 'thanks', 'thank you', 'bye', 'goodbye',
                 'help', 'what can you do', 'who are you', 'how\'s it going']
    
    if any(msg == g or msg.startswith(g + ' ') or msg.startswith(g + ',') or msg.startswith(g + '!') for g in greetings):
        return None
    
    # General knowledge questions - let AI handle without stock lookup
    general_topics = ['weather', 'news', 'explain', 'what is', 'who is', 'how does', 'why do', 
                      'tell me about', 'opinion on', 'think about', 'thoughts on', 'advice',
                      'recommend a', 'suggest a', 'help me', 'can you']
    
    # If it's clearly a general question without stock mentions, skip stock analysis
    is_general = any(t in msg for t in general_topics)
    has_company = any(c in msg for c in COMPANY_TO_TICKER.keys())
    
    if is_general and not has_company and 'stock' not in msg and 'invest' not in msg:
        return None
    
    # ===== AUTO-DETECT MARKET =====
    # Indian market indicators
    indian_indicators = ['nifty', 'sensex', 'bse', 'nse', 'rupee', '₹', 'india', 'indian',
                         'reliance', 'tcs', 'infosys', 'hdfc', 'icici', 'bharti', 'airtel',
                         'wipro', 'hcl', 'adani', 'tata', 'bajaj', 'kotak', 'sbi', 'axis',
                         'maruti', 'asian paints', 'titan', 'sun pharma', 'mahindra', 'larsen']
    
    # US market indicators  
    us_indicators = ['nasdaq', 's&p', 'sp500', 'dow', 'nyse', 'dollar', '$', 'us', 'american',
                     'apple', 'microsoft', 'google', 'amazon', 'meta', 'tesla', 'nvidia', 
                     'amd', 'intel', 'netflix', 'disney', 'nike', 'coca cola', 'pepsi',
                     'walmart', 'costco', 'starbucks', 'mcdonalds', 'boeing', 'ford']
    
    # Check for market hints in message
    has_indian = any(ind in msg for ind in indian_indicators)
    has_us = any(ind in msg for ind in us_indicators)
    
    # Auto-switch market if clear indicator (and not conflicting)
    if has_indian and not has_us:
        if st.session_state.get('market') != 'India':
            st.session_state.market = 'India'
    elif has_us and not has_indian:
        if st.session_state.get('market') != 'US':
            st.session_state.market = 'US'
    
    market = st.session_state.get('market', 'US')
    
    # Determine which stock list to use based on query
    stock_list = None
    scan_all = False  # Whether to scan beyond main indices
    
    if 'nasdaq' in msg or 'nasdaq 100' in msg or 'nasdaq100' in msg:
        stock_list = NASDAQ_100
    elif 's&p' in msg or 'sp500' in msg or 's&p 500' in msg or 'sp 500' in msg:
        stock_list = SP500_TOP
    elif 'nifty' in msg or 'nifty 50' in msg or 'nifty50' in msg:
        stock_list = NIFTY_50
        st.session_state.market = 'India'  # Auto-switch for NIFTY
    elif any(w in msg for w in ['all stocks', 'any stock', 'all market', 'trending', 'hot stocks', 'small cap', 'mid cap', 'meme']):
        scan_all = True  # Scan beyond main indices
    
    # ===== SMART DISCOVERY SCANS (News-based, dynamic) =====
    # Stocks in the news
    if any(w in msg for w in ['in the news', 'news today', 'whats in the news', "what's in the news", 'being talked about', 'headlines']):
        return screen_smart('news')
    
    # Hot/trending/movers - use smart scan
    if any(w in msg for w in ['hot', 'trending', 'movers', 'moving', 'action', 'whats moving', "what's moving"]):
        return screen_smart('hot')
    
    # ===== PERFORMANCE-BASED QUERIES =====
    # Weekly performance
    if any(w in msg for w in ['this week', 'weekly', 'week', '1w', 'past week', 'last week']):
        if any(w in msg for w in ['best', 'top', 'winner', 'gainer', 'up', 'hot']):
            return screen_by_performance('1w', 'gainers')
        if any(w in msg for w in ['worst', 'loser', 'down', 'falling']):
            return screen_by_performance('1w', 'losers')
    
    # Monthly performance
    if any(w in msg for w in ['this month', 'monthly', 'month', '1m', 'past month', 'last month', '30 day']):
        if any(w in msg for w in ['best', 'top', 'winner', 'gainer', 'up', 'hot']):
            return screen_by_performance('1m', 'gainers')
        if any(w in msg for w in ['worst', 'loser', 'down', 'falling']):
            return screen_by_performance('1m', 'losers')
    
    # YTD performance
    if any(w in msg for w in ['ytd', 'year to date', 'this year']):
        if any(w in msg for w in ['best', 'top', 'winner', 'gainer', 'up']):
            return screen_by_performance('ytd', 'gainers')
        if any(w in msg for w in ['worst', 'loser', 'down']):
            return screen_by_performance('ytd', 'losers')
    
    # 3 month / quarterly performance
    if any(w in msg for w in ['3 month', '3m', 'quarter', 'quarterly', '90 day']):
        if any(w in msg for w in ['best', 'top', 'winner', 'gainer', 'up']):
            return screen_by_performance('3m', 'gainers')
        if any(w in msg for w in ['worst', 'loser', 'down']):
            return screen_by_performance('3m', 'losers')
    
    # ===== SPECIAL SCANS =====
    # Breakout stocks
    if any(w in msg for w in ['breakout', 'breaking out', '52 week high', '52w high', 'new high', 'all time high', 'ath']):
        return find_breakout_stocks()
    
    # Oversold bounce plays
    if any(w in msg for w in ['oversold', 'bounce', 'beaten down', 'crashed', 'capitulation', 'bottom']):
        return find_oversold_bounces()
    
    # Today's gainers/losers - use smart scan
    if any(w in msg for w in ['gainer', 'gaining', 'up today', 'rising', 'green']):
        if not stock_list:  # If no specific index, use smart scan
            return screen_smart('gainers')
        return screen_by_strategy("top_gainers", stock_list)
    
    if any(w in msg for w in ['loser', 'losing', 'down today', 'falling', 'dropping', 'red']):
        if not stock_list:
            return screen_smart('losers')
        return screen_by_strategy("top_losers", stock_list)
    
    # Strategy-based queries
    if any(w in msg for w in ['best', 'top', 'recommend', 'suggest', 'find', 'scan', 'screen', 'search']) and ('stock' in msg or stock_list or scan_all):
        if any(w in msg for w in ['momentum', 'performing', 'performer', 'winners', 'gaining']):
            if stock_list:
                return screen_by_strategy("momentum", stock_list)
            return screen_smart('momentum')
        if any(w in msg for w in ['value', 'undervalued', 'cheap', 'bargain']):
            return screen_by_strategy("value", stock_list)
        if any(w in msg for w in ['quality', 'strong', 'solid', 'reliable']):
            return screen_by_strategy("quality", stock_list)
        if any(w in msg for w in ['dividend', 'yield', 'income', 'passive']):
            return screen_by_strategy("dividend", stock_list)
        if any(w in msg for w in ['large', 'biggest', 'largest', 'mega', 'blue chip', 'bluechip']):
            return screen_by_strategy("large_cap", stock_list)
        if any(w in msg for w in ['low pe', 'low p/e', 'cheap pe', 'lowest pe']):
            return screen_by_strategy("low_pe", stock_list)
        if any(w in msg for w in ['growth', 'growing', 'fast growing']):
            return screen_by_strategy("quality", stock_list)
        # Default: use smart scan for generic "best stocks" queries
        if scan_all or ('stock' in msg and not stock_list):
            return screen_smart('hot')
        if 'best' in msg and not stock_list:
            return screen_smart('hot')
        if stock_list:
            return screen_by_strategy("quality", stock_list)
    
    # Top gainers / losers
    if any(w in msg for w in ['gainer', 'gaining', 'up today', 'rising']):
        return screen_by_strategy("top_gainers", stock_list or (NASDAQ_100 if market == 'US' else NIFTY_50))
    if any(w in msg for w in ['loser', 'losing', 'down today', 'falling', 'dropping']):
        return screen_by_strategy("top_losers", stock_list or (NASDAQ_100 if market == 'US' else NIFTY_50))
    
    # Simple screening keywords
    if any(w in msg for w in ['undervalued', 'value stocks', 'cheap stocks']): 
        return screen_stocks("undervalued")
    if any(w in msg for w in ['growth stocks', 'growing companies']): 
        return screen_stocks("growth")
    if any(w in msg for w in ['dividend stocks', 'income stocks']): 
        return screen_stocks("dividend")
    
    # ===== SIMPLE PRICE QUERIES =====
    # Check if this is just a simple "what is X price" query
    is_simple_price_query = any(w in msg for w in ['price of', 'price for', 'how much is', 'what is', 'whats the price', "what's the price", 'current price', 'stock price'])
    
    # Check for stock-related intent
    stock_intent_words = ['stock', 'price', 'analyze', 'analysis', 'ticker', 'share', 'shares', 
                          'buy', 'sell', 'invest', 'trading', 'market cap', 'pe ratio', 'compare',
                          'chart', 'graph']
    has_stock_intent = any(w in msg for w in stock_intent_words)
    
    # For simple price queries, try to get quick accurate price
    if is_simple_price_query:
        # Try to find the ticker
        ticker_from_name = get_ticker_from_name(msg)
        if ticker_from_name:
            full_ticker = f"{ticker_from_name}.NS" if market == 'India' else ticker_from_name
            quick = get_quick_price(full_ticker)
            if quick:
                currency = '₹' if market == 'India' else '$'
                color = "🟢" if quick['change_pct'] >= 0 else "🔴"
                return {
                    "success": True,
                    "type": "quick_price",
                    "ticker": ticker_from_name,
                    "price": f"{currency}{quick['price']:,.2f}",
                    "change": f"{color} {quick['change']:+.2f} ({quick['change_pct']:+.2f}%)",
                }
        
        # Check for company names
        for company_name, ticker in COMPANY_TO_TICKER.items():
            if company_name in msg:
                full_ticker = f"{ticker}.NS" if market == 'India' else ticker
                quick = get_quick_price(full_ticker)
                if quick:
                    currency = '₹' if market == 'India' else '$'
                    color = "🟢" if quick['change_pct'] >= 0 else "🔴"
                    return {
                        "success": True,
                        "type": "quick_price",
                        "ticker": ticker,
                        "price": f"{currency}{quick['price']:,.2f}",
                        "change": f"{color} {quick['change']:+.2f} ({quick['change_pct']:+.2f}%)",
                    }
    
    # Handle comparisons
    if any(w in msg for w in ['compare', 'vs', 'versus']):
        found_tickers = []
        for company_name, ticker in COMPANY_TO_TICKER.items():
            if company_name in msg:
                if ticker not in found_tickers:
                    found_tickers.append(ticker)
        ticker_matches = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'OR', 'COMPARE', 'WITH', 'NASDAQ', 'NIFTY']
        for t in ticker_matches:
            if t not in exclude and t not in found_tickers:
                found_tickers.append(t)
        if len(found_tickers) >= 2:
            return compare_stocks(','.join(found_tickers))
    
    # Check for company names
    ticker_from_name = get_ticker_from_name(msg)
    if ticker_from_name:
        return analyze_stock(ticker_from_name, show_chart=show_chart)
    
    for company_name in COMPANY_TO_TICKER.keys():
        if company_name in msg:
            return analyze_stock(COMPANY_TO_TICKER[company_name], show_chart=show_chart)
    
    # Look for ticker symbols if there's stock intent
    if has_stock_intent:
        tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'AI', 'OK', 'HI', 'RSI', 'MACD', 
                   'ANALYZE', 'ANALYSIS', 'TELL', 'ME', 'ABOUT', 'SHOW', 'GET', 'FIND', 
                   'STOCK', 'PRICE', 'BUY', 'SELL', 'WHAT', 'HOW', 'WHY', 'CAN', 'YOU',
                   'CHART', 'GRAPH', 'NASDAQ', 'NIFTY', 'TOP', 'BEST']
        
        for t in tickers:
            if t in US_STOCKS and t not in exclude: 
                return analyze_stock(t, show_chart=show_chart)
            if t in NASDAQ_100 and t not in exclude: 
                return analyze_stock(t, show_chart=show_chart)
            if t in SP500_TOP and t not in exclude: 
                return analyze_stock(t, show_chart=show_chart)
        
        indian_names = [s.replace('.NS', '') for s in INDIAN_STOCKS + NIFTY_50]
        for t in tickers:
            if t in indian_names and t not in exclude: 
                return analyze_stock(t, show_chart=show_chart)
        
        for t in tickers:
            if t not in exclude and len(t) >= 3: 
                return analyze_stock(t, show_chart=show_chart)
    
    return None

def process_message(user_message, history):
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not api_key: return "Add GROQ_API_KEY to secrets", None
    
    data = detect_and_execute(user_message)
    client = Groq(api_key=api_key)
    market = st.session_state.get('market', 'US')
    
    # Check if data fetch failed
    if data and data.get("success") == False and data.get("error"):
        return f"⚠️ {data.get('error')}\n\nPlease try again or check if the ticker symbol is correct.", data
    
    system = f"""You are Paula, a stock analysis assistant with LIVE market data access.

CRITICAL: You have REAL-TIME stock data. When stock data is provided below, USE IT - don't say you can't access prices or suggest checking other websites. The data is LIVE and ACCURATE.

Market: {market} | Date: {datetime.now().strftime("%Y-%m-%d")}

When you receive stock data in the "ANALYSIS DATA" section below, you MUST:
1. Use the exact price, change %, and other numbers provided
2. Give a trading verdict based on the data
3. NEVER say "I don't have access to real-time data" - YOU DO HAVE IT
4. NEVER say "I'm a large language model" - just analyze the data

For stock analysis, follow this structure:

**TRADING VERDICT**
- State the trading_rating (🟢 STRONG BUY, 🟢 BUY, 🟡 HOLD, 🟠 CAUTION, 🔴 AVOID)
- Give the score (e.g., "Score: 72/100")
- One-line action recommendation

**KEY SIGNALS**
- List buy_signals from the data
- Note RSI, MACD, volume signals

**CATALYSTS & NEWS**
- Summarize news sentiment
- Note upcoming earnings if available

**VALUATION**
- P/E, Forward P/E, PEG ratio
- Analyst targets and upside %

**TECHNICALS**
- Price vs SMAs
- RSI, Bollinger position
- Momentum

**RISKS**
- List any warnings from the data

**TRADING PLAN**
- Entry zone, stop loss, target price

Be direct. Use the provided data. Never claim you lack access to prices."""

    messages = [{"role": "system", "content": system}]
    for m in history[-6:]: messages.append({"role": m["role"], "content": m["content"]})
    
    if data and data.get("success"):
        data_for_ai = {k: v for k, v in data.items() if k != 'table'}
        if 'table' in data: 
            data_for_ai['top_stocks'] = [row.get('Ticker', '') for row in data['table'][:5]]
        
        # Build prompt with all context - make it very clear this is real data
        prompt_parts = [
            f"User asked: {user_message}",
            f"\n\n=== LIVE STOCK DATA (USE THIS - IT'S REAL-TIME) ===\n{json.dumps(data_for_ai, indent=2, default=str)}"
        ]
        
        # Add news if available
        if data.get('news'):
            prompt_parts.append(f"\n=== RECENT NEWS ===\n{data['news']}")
        if data.get('market_news'):
            prompt_parts.append(f"\n=== MARKET NEWS ===\n{data['market_news']}")
        
        prompt_parts.append("\n\nIMPORTANT: Analyze using the EXACT data above. State the price shown. Give your trading verdict. Do NOT say you don't have data - it's right there above.")
        prompt = "\n".join(prompt_parts)
    else:
        prompt = user_message
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=messages, 
            max_tokens=1500, 
            temperature=0.7
        )
        return response.choices[0].message.content, data
    except Exception as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            return "⚠️ Rate limit reached. Please wait a moment and try again.", None
        elif "api key" in error_msg.lower() or "authentication" in error_msg.lower():
            return "⚠️ API key issue. Please check your GROQ_API_KEY in settings.", None
        elif "timeout" in error_msg.lower():
            return "⚠️ Request timed out. Please try again.", None
        else:
            return f"⚠️ An error occurred: {error_msg[:100]}", None

# ==================== DISPLAY ====================
def display_table(data):
    if "table" in data and data["table"]:
        st.dataframe(pd.DataFrame(data["table"]), use_container_width=True, hide_index=True)

def display_charts():
    charts = st.session_state.get('charts_to_display', [])
    if not charts: return
    
    st.markdown("#### Price Chart")
    period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y"], index=2, key="chart_period", label_visibility="collapsed")
    
    for i, ticker in enumerate(charts[:3]):
        fig = create_technical_chart(ticker, period)
        if fig: 
            st.plotly_chart(fig, use_container_width=True, key=f"chart_main_{ticker}_{i}")

def display_charts_inline(charts, msg_index=0):
    """Display charts inline with a message"""
    if not charts: return
    
    period = "6mo"
    for i, ticker in enumerate(charts[:3]):
        fig = create_technical_chart(ticker, period)
        if fig: 
            st.plotly_chart(fig, use_container_width=True, key=f"chart_inline_{msg_index}_{ticker}_{i}")

def process_and_display(prompt):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.spinner("Analyzing..."):
        response, data = process_message(prompt, st.session_state.chat_messages[:-1])
    
    msg_data = {"role": "assistant", "content": response}
    if data and "table" in data: 
        msg_data["table_data"] = data
    
    # Store charts WITH the message, not globally
    if st.session_state.charts_to_display:
        msg_data["charts"] = st.session_state.charts_to_display.copy()
        st.session_state.charts_to_display = []  # Clear global
    
    st.session_state.chat_messages.append(msg_data)

# ==================== MAIN ====================
def main():
    # Init state
    if 'chat_messages' not in st.session_state: st.session_state.chat_messages = []
    if 'market' not in st.session_state: st.session_state.market = 'US'
    if 'charts_to_display' not in st.session_state: st.session_state.charts_to_display = []
    if 'show_charts' not in st.session_state: st.session_state.show_charts = True
    
    # Header row
    header_col1, header_col2 = st.columns([6, 1])
    with header_col1:
        st.markdown('<div class="main-header"><h1>Paula</h1><p>Stock Analysis Assistant</p></div>', unsafe_allow_html=True)
    with header_col2:
        # Small market indicator (auto-switches based on query)
        flag = "🇺🇸" if st.session_state.market == "US" else "🇮🇳"
        st.markdown(f'<p style="text-align:right;color:#52525b;font-size:12px;margin-top:20px;">{flag} {st.session_state.market}</p>', unsafe_allow_html=True)
    
    # Settings (collapsible)
    with st.expander("⚙️ Settings", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            show_charts = st.checkbox("Show charts automatically", value=st.session_state.show_charts)
            if show_charts != st.session_state.show_charts:
                st.session_state.show_charts = show_charts
        with col2:
            market_options = ['US', 'India']
            current_idx = 0 if st.session_state.market == 'US' else 1
            new_market = st.selectbox("Market", market_options, index=current_idx)
            if new_market != st.session_state.market:
                st.session_state.market = new_market
                st.rerun()
        with col3:
            if st.button("Clear chat"):
                st.session_state.chat_messages = []
                st.session_state.charts_to_display = []
                st.rerun()
    
    # API check
    if not (st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")):
        st.error("Add GROQ_API_KEY to secrets")
        return
    
    # Main content area
    if st.session_state.chat_messages:
        # Show chat history
        for idx, m in enumerate(st.session_state.chat_messages):
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                if m.get("table_data"): 
                    display_table(m["table_data"])
                # Show charts inline with this message
                if m.get("charts"):
                    display_charts_inline(m["charts"], idx)
    else:
        # Welcome state - simple and clean
        st.markdown("")
        st.markdown("")
        st.markdown('<p style="color:#71717a;text-align:center;">Ask me about any stock, anywhere.</p>', unsafe_allow_html=True)
    
    # Input area
    st.markdown("---")
    input_col1, input_col2 = st.columns([12, 1])
    
    with input_col1:
        def submit_text():
            if st.session_state.get('text_input_value'):
                st.session_state.pending_message = st.session_state.text_input_value
                st.session_state.text_input_value = ""
        
        st.text_input(
            "Message",
            placeholder="Ask about any stock...",
            key="text_input_value",
            on_change=submit_text,
            label_visibility="collapsed"
        )
    
    with input_col2:
        try:
            from streamlit_mic_recorder import speech_to_text
            voice_text = speech_to_text(
                language='en',
                start_prompt="🎤",
                stop_prompt="■",
                just_once=True,
                use_container_width=True,
                key='voice_input'
            )
        except ImportError:
            voice_text = None
    
    # Process pending message
    if st.session_state.get('pending_message'):
        msg = st.session_state.pending_message
        st.session_state.pending_message = None
        process_and_display(msg)
        st.rerun()
    
    # Process voice input
    if voice_text:
        process_and_display(voice_text)
        st.rerun()
    
    # Disclaimer footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align:center;color:#52525b;font-size:11px;">'
        '⚠️ <strong>Disclaimer:</strong> This is for educational purposes only, not financial advice. '
        'Always do your own research before investing. Data may be delayed or inaccurate.'
        '</p>', 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
