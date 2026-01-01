import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import json
import os
from dotenv import load_dotenv
import re
from groq import Groq

warnings.filterwarnings('ignore')
load_dotenv()

st.set_page_config(
    page_title="AI Stock Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

st.markdown("""
<style>
    /* Force dark mode on all devices */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
        color: #ffffff !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        font-weight: 600 !important;
    }
    
    p, span, div, label, .stMarkdown {
        color: #e5e7eb !important;
    }
    
    .stChatFloatingInputContainer {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
    }
    
    .stChatMessage {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        margin: 0.5rem 0 !important;
        color: #ffffff !important;
    }
    
    input, textarea, .stTextInput input, .stTextArea textarea {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        transform: translateY(-2px);
    }
    
    .stMetric {
        background: rgba(255, 255, 255, 0.05) !important;
        padding: 1rem !important;
        border-radius: 8px !important;
    }
    
    .stMetric label { color: #9ca3af !important; }
    .stMetric [data-testid="stMetricValue"] { color: #ffffff !important; }
    
    .stDataFrame, table {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #ffffff !important;
    }
    
    .stDataFrame th {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
    }
    
    .stDataFrame td { color: #e5e7eb !important; }
    
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #ffffff !important;
    }
    
    a { color: #60a5fa !important; }
    a:hover { color: #93c5fd !important; }
    
    code {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #fbbf24 !important;
        padding: 0.2rem 0.4rem !important;
        border-radius: 4px !important;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        color: #ffffff;
        padding: 8px 16px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==================== STOCK UNIVERSES ====================

# US Stocks - S&P 500 Top 100
US_STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'V', 'UNH',
    'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'XOM', 'HD', 'CVX', 'MRK', 'ABBV',
    'PEP', 'KO', 'AVGO', 'COST', 'LLY', 'TMO', 'ACN', 'MCD', 'CSCO', 'ABT',
    'DHR', 'CRM', 'VZ', 'ADBE', 'NKE', 'NEE', 'WFC', 'TXN', 'PM', 'UPS',
    'RTX', 'HON', 'ORCL', 'BMY', 'QCOM', 'UNP', 'INTU', 'LOW', 'AMD', 'COP',
    'BA', 'AMGN', 'SPGI', 'GE', 'CAT', 'PLD', 'SBUX', 'GILD', 'DE', 'MMC',
    'ADP', 'CI', 'CVS', 'MDLZ', 'TJX', 'SYK', 'ZTS', 'BDX', 'NOW', 'REGN',
    'MO', 'AXP', 'BLK', 'DUK', 'CB', 'SO', 'PNC', 'USB', 'SLB', 'ITW',
    'BSX', 'C', 'EOG', 'HUM', 'LRCX', 'SCHW', 'MMM', 'ETN', 'TGT', 'AON',
    'GD', 'ISRG', 'MU', 'FIS', 'NSC', 'EL', 'SHW', 'CL', 'KLAC', 'APD'
]

# Indian Stocks - NIFTY 50 + Popular Stocks (NSE)
INDIAN_STOCKS = [
    # NIFTY 50
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'HCLTECH.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS',
    'SUNPHARMA.NS', 'TITAN.NS', 'BAJFINANCE.NS', 'DMART.NS', 'WIPRO.NS',
    'ULTRACEMCO.NS', 'ONGC.NS', 'NTPC.NS', 'POWERGRID.NS', 'M&M.NS',
    'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'ADANIENT.NS', 'ADANIPORTS.NS',
    'COALINDIA.NS', 'BAJAJFINSV.NS', 'TECHM.NS', 'HDFCLIFE.NS', 'SBILIFE.NS',
    'GRASIM.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS', 'APOLLOHOSP.NS',
    'EICHERMOT.NS', 'BRITANNIA.NS', 'NESTLEIND.NS', 'INDUSINDBK.NS', 'HEROMOTOCO.NS',
    'BAJAJ-AUTO.NS', 'TATACONSUM.NS', 'HINDALCO.NS', 'BPCL.NS', 'UPL.NS',
    # Additional Popular Indian Stocks
    'ZOMATO.NS', 'PAYTM.NS', 'NYKAA.NS', 'POLICYBZR.NS', 'IRCTC.NS',
    'HAL.NS', 'BEL.NS', 'IRFC.NS', 'INDIANB.NS', 'PNB.NS',
    'BANKBARODA.NS', 'CANBK.NS', 'VEDL.NS', 'TATAPOWER.NS', 'ADANIGREEN.NS',
    'ADANIPOWER.NS', 'AMBUJACEM.NS', 'ACC.NS', 'SHREECEM.NS', 'PIDILITIND.NS',
    'HAVELLS.NS', 'VOLTAS.NS', 'GODREJCP.NS', 'MARICO.NS', 'COLPAL.NS',
    'DABUR.NS', 'BERGEPAINT.NS', 'PAGEIND.NS', 'MUTHOOTFIN.NS', 'CHOLAFIN.NS',
    'BAJAJHLDNG.NS', 'SIEMENS.NS', 'ABB.NS', 'CGPOWER.NS', 'BHEL.NS'
]

# Display names for Indian stocks (without .NS suffix)
INDIAN_STOCK_NAMES = {ticker: ticker.replace('.NS', '') for ticker in INDIAN_STOCKS}

# Session state
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'market' not in st.session_state:
    st.session_state.market = 'US'  # Default to US market

# ==================== HELPER FUNCTIONS ====================

def get_stock_list():
    """Get current stock list based on selected market"""
    if st.session_state.market == 'India':
        return INDIAN_STOCKS
    return US_STOCKS


def get_currency_symbol():
    """Get currency symbol based on market"""
    if st.session_state.market == 'India':
        return '₹'
    return '$'


def format_market_cap(value, market='US'):
    """Format market cap to readable string"""
    if value is None:
        return "N/A"
    
    symbol = '₹' if market == 'India' else '$'
    
    if value >= 1e12:
        return f"{symbol}{value/1e12:.2f}T"
    elif value >= 1e9:
        return f"{symbol}{value/1e9:.2f}B"
    elif value >= 1e7:
        return f"{symbol}{value/1e7:.2f}Cr"  # Crores for Indian market
    elif value >= 1e6:
        return f"{symbol}{value/1e6:.2f}M"
    else:
        return f"{symbol}{value:,.0f}"


def format_price(value, market='US'):
    """Format price with currency symbol"""
    if value is None:
        return "N/A"
    symbol = '₹' if market == 'India' else '$'
    return f"{symbol}{value:,.2f}"


def get_display_ticker(ticker):
    """Get display name for ticker (removes .NS suffix for Indian stocks)"""
    return ticker.replace('.NS', '').replace('.BO', '')


def normalize_ticker(ticker, market='US'):
    """Add appropriate suffix for market"""
    ticker = ticker.upper().strip()
    
    # Remove any existing suffix
    ticker = ticker.replace('.NS', '').replace('.BO', '')
    
    if market == 'India':
        # Check if it's a known Indian stock
        if f"{ticker}.NS" in INDIAN_STOCKS:
            return f"{ticker}.NS"
        return f"{ticker}.NS"  # Default to NSE
    
    return ticker


# ==================== LIVE DATA FUNCTIONS ====================

@st.cache_data(ttl=300)
def get_live_price(ticker):
    """Get live/recent price data"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='5d')
        if hist.empty:
            return None
        
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100
        
        return {
            "price": round(current_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "high": round(hist['High'].iloc[-1], 2),
            "low": round(hist['Low'].iloc[-1], 2),
            "volume": int(hist['Volume'].iloc[-1])
        }
    except:
        return None


@st.cache_data(ttl=900)
def get_stock_fundamentals(ticker):
    """Get comprehensive fundamental data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or 'symbol' not in info:
            return None
        
        # Determine market
        market = 'India' if '.NS' in ticker or '.BO' in ticker else 'US'
        
        # Get price data
        hist = stock.history(period='1y')
        if hist.empty:
            return None
        
        current_price = hist['Close'].iloc[-1]
        
        # Calculate YTD performance
        year_ago_price = hist['Close'].iloc[0] if len(hist) > 200 else current_price
        ytd_change = ((current_price - year_ago_price) / year_ago_price) * 100
        
        # Calculate growth metrics
        revenue_growth = None
        earnings_growth = None
        
        try:
            financials = stock.financials
            if financials is not None and not financials.empty and len(financials.columns) >= 2:
                if 'Total Revenue' in financials.index:
                    recent_rev = financials.loc['Total Revenue'].iloc[0]
                    old_rev = financials.loc['Total Revenue'].iloc[-1]
                    if old_rev and old_rev != 0:
                        revenue_growth = ((recent_rev - old_rev) / abs(old_rev)) * 100
                
                if 'Net Income' in financials.index:
                    recent_earn = financials.loc['Net Income'].iloc[0]
                    old_earn = financials.loc['Net Income'].iloc[-1]
                    if old_earn and old_earn != 0:
                        earnings_growth = ((recent_earn - old_earn) / abs(old_earn)) * 100
        except:
            pass
        
        fundamentals = {
            "ticker": ticker,
            "display_ticker": get_display_ticker(ticker),
            "name": info.get('longName', info.get('shortName', get_display_ticker(ticker))),
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "market": market,
            "market_cap": info.get('marketCap'),
            "market_cap_fmt": format_market_cap(info.get('marketCap'), market),
            "price": round(current_price, 2),
            "price_fmt": format_price(current_price, market),
            "ytd_change": round(ytd_change, 2) if ytd_change else None,
            "currency": info.get('currency', 'INR' if market == 'India' else 'USD'),
            
            # Valuation
            "pe_ratio": info.get('trailingPE'),
            "forward_pe": info.get('forwardPE'),
            "peg_ratio": info.get('pegRatio'),
            "price_to_book": info.get('priceToBook'),
            "price_to_sales": info.get('priceToSalesTrailing12Months'),
            "ev_to_ebitda": info.get('enterpriseToEbitda'),
            
            # Profitability
            "profit_margin": info.get('profitMargins'),
            "operating_margin": info.get('operatingMargins'),
            "roe": info.get('returnOnEquity'),
            "roa": info.get('returnOnAssets'),
            
            # Financial Health
            "debt_to_equity": info.get('debtToEquity'),
            "current_ratio": info.get('currentRatio'),
            "quick_ratio": info.get('quickRatio'),
            "total_debt": info.get('totalDebt'),
            "total_cash": info.get('totalCash'),
            
            # Growth
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "earnings_per_share": info.get('trailingEps'),
            
            # Dividends
            "dividend_yield": info.get('dividendYield'),
            "payout_ratio": info.get('payoutRatio'),
            "dividend_rate": info.get('dividendRate'),
            
            # Trading Info
            "beta": info.get('beta'),
            "52_week_high": info.get('fiftyTwoWeekHigh'),
            "52_week_low": info.get('fiftyTwoWeekLow'),
            "avg_volume": info.get('averageVolume'),
            
            # Description
            "business_summary": info.get('longBusinessSummary', 'No description available.')
        }
        
        return fundamentals
        
    except Exception as e:
        return None


# ==================== STOCK SCREENING TOOLS ====================

def find_undervalued_stocks_tool(max_pe=20, min_roe=12):
    """Find undervalued stocks"""
    try:
        results = []
        stock_list = get_stock_list()
        market = st.session_state.market
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, ticker in enumerate(stock_list):
            progress_bar.progress((idx + 1) / len(stock_list))
            status_text.text(f"Scanning {get_display_ticker(ticker)}... ({idx+1}/{len(stock_list)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            pe = fundamentals['pe_ratio']
            roe = fundamentals['roe']
            
            if pe and pe > 0 and pe < max_pe:
                if roe and roe * 100 > min_roe:
                    results.append({
                        "ticker": fundamentals['display_ticker'],
                        "name": fundamentals['name'],
                        "price": fundamentals['price_fmt'],
                        "market_cap": fundamentals['market_cap_fmt'],
                        "pe_ratio": round(pe, 2),
                        "roe": f"{roe * 100:.1f}%",
                        "profit_margin": f"{fundamentals['profit_margin'] * 100:.1f}%" if fundamentals['profit_margin'] else "N/A",
                        "sector": fundamentals['sector']
                    })
        
        progress_bar.empty()
        status_text.empty()
        
        if results:
            results = sorted(results, key=lambda x: x['pe_ratio'])
            return {
                "success": True,
                "market": market,
                "criteria": f"PE < {max_pe}, ROE > {min_roe}%",
                "total_found": len(results),
                "stocks": results[:15]
            }
        else:
            return {"success": False, "message": "No undervalued stocks found matching criteria."}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


def find_high_growth_stocks_tool(min_revenue_growth=15, min_roe=10):
    """Find high growth stocks"""
    try:
        results = []
        stock_list = get_stock_list()
        market = st.session_state.market
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, ticker in enumerate(stock_list):
            progress_bar.progress((idx + 1) / len(stock_list))
            status_text.text(f"Scanning {get_display_ticker(ticker)}... ({idx+1}/{len(stock_list)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            rev_growth = fundamentals['revenue_growth']
            roe = fundamentals['roe']
            
            if rev_growth and rev_growth > min_revenue_growth:
                if roe and roe * 100 > min_roe:
                    results.append({
                        "ticker": fundamentals['display_ticker'],
                        "name": fundamentals['name'],
                        "price": fundamentals['price_fmt'],
                        "market_cap": fundamentals['market_cap_fmt'],
                        "revenue_growth": f"{rev_growth:.1f}%",
                        "roe": f"{roe * 100:.1f}%",
                        "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else "N/A",
                        "sector": fundamentals['sector']
                    })
        
        progress_bar.empty()
        status_text.empty()
        
        if results:
            results = sorted(results, key=lambda x: float(x['revenue_growth'].replace('%', '')), reverse=True)
            return {
                "success": True,
                "market": market,
                "criteria": f"Revenue Growth > {min_revenue_growth}%, ROE > {min_roe}%",
                "total_found": len(results),
                "stocks": results[:15]
            }
        else:
            return {"success": False, "message": "No high growth stocks found."}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


def find_dividend_stocks_tool(min_yield=2.0):
    """Find high dividend yield stocks"""
    try:
        results = []
        stock_list = get_stock_list()
        market = st.session_state.market
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, ticker in enumerate(stock_list):
            progress_bar.progress((idx + 1) / len(stock_list))
            status_text.text(f"Scanning {get_display_ticker(ticker)}... ({idx+1}/{len(stock_list)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            div_yield = fundamentals['dividend_yield']
            
            if div_yield:
                yield_pct = div_yield * 100
                if yield_pct >= min_yield:
                    results.append({
                        "ticker": fundamentals['display_ticker'],
                        "name": fundamentals['name'],
                        "price": fundamentals['price_fmt'],
                        "market_cap": fundamentals['market_cap_fmt'],
                        "dividend_yield": f"{yield_pct:.2f}%",
                        "payout_ratio": f"{fundamentals['payout_ratio'] * 100:.1f}%" if fundamentals['payout_ratio'] else "N/A",
                        "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else "N/A",
                        "sector": fundamentals['sector']
                    })
        
        progress_bar.empty()
        status_text.empty()
        
        if results:
            results = sorted(results, key=lambda x: float(x['dividend_yield'].replace('%', '')), reverse=True)
            return {
                "success": True,
                "market": market,
                "criteria": f"Dividend Yield >= {min_yield}%",
                "total_found": len(results),
                "stocks": results[:15]
            }
        else:
            return {"success": False, "message": "No dividend stocks found."}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_company_tool(ticker):
    """Deep dive analysis of a company"""
    try:
        # Normalize ticker based on current market
        original_ticker = ticker.upper().strip()
        market = st.session_state.market
        
        # Try to find the stock
        if market == 'India':
            if not original_ticker.endswith('.NS') and not original_ticker.endswith('.BO'):
                ticker = f"{original_ticker}.NS"
            else:
                ticker = original_ticker
        else:
            ticker = original_ticker.replace('.NS', '').replace('.BO', '')
        
        fundamentals = get_stock_fundamentals(ticker)
        
        # If not found in current market, try the other market
        if not fundamentals:
            if market == 'India':
                fundamentals = get_stock_fundamentals(original_ticker)  # Try US
            else:
                fundamentals = get_stock_fundamentals(f"{original_ticker}.NS")  # Try India
        
        if not fundamentals:
            return {"success": False, "error": f"Could not fetch data for {original_ticker}. Please check the ticker symbol."}
        
        # Get live price
        live_data = get_live_price(fundamentals['ticker'])
        stock_market = fundamentals['market']
        
        # Calculate scores
        valuation_score = 0
        if fundamentals['pe_ratio'] and fundamentals['pe_ratio'] < 25:
            valuation_score += 2 if fundamentals['pe_ratio'] < 15 else 1
        if fundamentals['peg_ratio'] and fundamentals['peg_ratio'] < 2:
            valuation_score += 2 if fundamentals['peg_ratio'] < 1 else 1
        if fundamentals['price_to_book'] and fundamentals['price_to_book'] < 3:
            valuation_score += 1
        
        profitability_score = 0
        if fundamentals['roe'] and fundamentals['roe'] > 0.12:
            profitability_score += 2 if fundamentals['roe'] > 0.20 else 1
        if fundamentals['profit_margin'] and fundamentals['profit_margin'] > 0.10:
            profitability_score += 2 if fundamentals['profit_margin'] > 0.20 else 1
        if fundamentals['operating_margin'] and fundamentals['operating_margin'] > 0.15:
            profitability_score += 1
        
        health_score = 0
        if fundamentals['current_ratio'] and fundamentals['current_ratio'] > 1.2:
            health_score += 2 if fundamentals['current_ratio'] > 2 else 1
        if fundamentals['debt_to_equity'] and fundamentals['debt_to_equity'] < 100:
            health_score += 2 if fundamentals['debt_to_equity'] < 50 else 1
        
        total_score = valuation_score + profitability_score + health_score
        max_total = 14
        overall_pct = (total_score / max_total) * 100
        
        if overall_pct >= 70:
            rating, rating_emoji = "Strong Buy", "🟢"
        elif overall_pct >= 55:
            rating, rating_emoji = "Buy", "🟡"
        elif overall_pct >= 40:
            rating, rating_emoji = "Hold", "🟠"
        else:
            rating, rating_emoji = "Caution", "🔴"
        
        currency = '₹' if stock_market == 'India' else '$'
        
        return {
            "success": True,
            "company": {
                "ticker": fundamentals['display_ticker'],
                "name": fundamentals['name'],
                "sector": fundamentals['sector'],
                "industry": fundamentals['industry'],
                "market": stock_market,
                "price": f"{currency}{live_data['price']:,.2f}" if live_data else fundamentals['price_fmt'],
                "change": f"{live_data['change']:+.2f}" if live_data else "0.00",
                "change_pct": f"{live_data['change_pct']:+.2f}%" if live_data else "0.00%",
                "market_cap": fundamentals['market_cap_fmt']
            },
            "valuation": {
                "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else "N/A",
                "forward_pe": round(fundamentals['forward_pe'], 2) if fundamentals['forward_pe'] else "N/A",
                "peg_ratio": round(fundamentals['peg_ratio'], 2) if fundamentals['peg_ratio'] else "N/A",
                "price_to_book": round(fundamentals['price_to_book'], 2) if fundamentals['price_to_book'] else "N/A",
                "score": f"{valuation_score}/5"
            },
            "profitability": {
                "roe": f"{fundamentals['roe']*100:.2f}%" if fundamentals['roe'] else "N/A",
                "roa": f"{fundamentals['roa']*100:.2f}%" if fundamentals['roa'] else "N/A",
                "profit_margin": f"{fundamentals['profit_margin']*100:.2f}%" if fundamentals['profit_margin'] else "N/A",
                "operating_margin": f"{fundamentals['operating_margin']*100:.2f}%" if fundamentals['operating_margin'] else "N/A",
                "score": f"{profitability_score}/5"
            },
            "financial_health": {
                "debt_to_equity": round(fundamentals['debt_to_equity'], 2) if fundamentals['debt_to_equity'] else "N/A",
                "current_ratio": round(fundamentals['current_ratio'], 2) if fundamentals['current_ratio'] else "N/A",
                "total_cash": format_market_cap(fundamentals['total_cash'], stock_market),
                "total_debt": format_market_cap(fundamentals['total_debt'], stock_market),
                "score": f"{health_score}/4"
            },
            "growth": {
                "revenue_growth": f"{fundamentals['revenue_growth']:.2f}%" if fundamentals['revenue_growth'] else "N/A",
                "earnings_growth": f"{fundamentals['earnings_growth']:.2f}%" if fundamentals['earnings_growth'] else "N/A",
                "ytd_performance": f"{fundamentals['ytd_change']:.2f}%" if fundamentals['ytd_change'] else "N/A"
            },
            "dividends": {
                "dividend_yield": f"{fundamentals['dividend_yield']*100:.2f}%" if fundamentals['dividend_yield'] else "N/A",
                "payout_ratio": f"{fundamentals['payout_ratio']*100:.2f}%" if fundamentals['payout_ratio'] else "N/A"
            },
            "trading_info": {
                "52_week_high": f"{currency}{fundamentals['52_week_high']:.2f}" if fundamentals['52_week_high'] else "N/A",
                "52_week_low": f"{currency}{fundamentals['52_week_low']:.2f}" if fundamentals['52_week_low'] else "N/A",
                "beta": round(fundamentals['beta'], 2) if fundamentals['beta'] else "N/A",
                "avg_volume": f"{fundamentals['avg_volume']:,}" if fundamentals['avg_volume'] else "N/A"
            },
            "rating": {
                "overall_score": f"{total_score}/{max_total}",
                "percentage": round(overall_pct, 1),
                "recommendation": rating,
                "emoji": rating_emoji
            },
            "business_summary": fundamentals['business_summary'][:500] + "..." if len(str(fundamentals['business_summary'])) > 500 else fundamentals['business_summary']
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_companies_tool(tickers):
    """Compare multiple companies"""
    try:
        if isinstance(tickers, str):
            tickers = [t.strip().upper() for t in re.split(r'[,\s]+', tickers) if t.strip()]
        
        comparisons = []
        progress_bar = st.progress(0)
        market = st.session_state.market
        
        for idx, ticker in enumerate(tickers[:5]):
            progress_bar.progress((idx + 1) / min(len(tickers), 5))
            
            # Normalize ticker
            if market == 'India' and not ticker.endswith('.NS'):
                full_ticker = f"{ticker}.NS"
            else:
                full_ticker = ticker
            
            fundamentals = get_stock_fundamentals(full_ticker)
            
            # Try other market if not found
            if not fundamentals:
                alt_ticker = ticker if market == 'India' else f"{ticker}.NS"
                fundamentals = get_stock_fundamentals(alt_ticker)
            
            if not fundamentals:
                comparisons.append({"ticker": ticker, "error": "Could not fetch data"})
                continue
            
            live_data = get_live_price(fundamentals['ticker'])
            stock_market = fundamentals['market']
            currency = '₹' if stock_market == 'India' else '$'
            
            comparisons.append({
                "ticker": fundamentals['display_ticker'],
                "name": fundamentals['name'],
                "market": stock_market,
                "price": f"{currency}{live_data['price']:,.2f}" if live_data else fundamentals['price_fmt'],
                "change_pct": f"{live_data['change_pct']:+.2f}%" if live_data else "N/A",
                "market_cap": fundamentals['market_cap_fmt'],
                "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else "N/A",
                "roe": f"{fundamentals['roe']*100:.1f}%" if fundamentals['roe'] else "N/A",
                "profit_margin": f"{fundamentals['profit_margin']*100:.1f}%" if fundamentals['profit_margin'] else "N/A",
                "dividend_yield": f"{fundamentals['dividend_yield']*100:.2f}%" if fundamentals['dividend_yield'] else "N/A",
                "sector": fundamentals['sector']
            })
        
        progress_bar.empty()
        
        return {
            "success": True,
            "count": len(comparisons),
            "comparisons": comparisons
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_sector_stocks_tool(sector):
    """Get all stocks in a specific sector"""
    try:
        results = []
        stock_list = get_stock_list()
        market = st.session_state.market
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, ticker in enumerate(stock_list):
            progress_bar.progress((idx + 1) / len(stock_list))
            status_text.text(f"Scanning {get_display_ticker(ticker)}... ({idx+1}/{len(stock_list)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            if sector.lower() in fundamentals['sector'].lower():
                results.append({
                    "ticker": fundamentals['display_ticker'],
                    "name": fundamentals['name'],
                    "price": fundamentals['price_fmt'],
                    "market_cap": fundamentals['market_cap_fmt'],
                    "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else "N/A",
                    "roe": f"{fundamentals['roe']*100:.1f}%" if fundamentals['roe'] else "N/A",
                    "industry": fundamentals['industry']
                })
        
        progress_bar.empty()
        status_text.empty()
        
        if results:
            return {
                "success": True,
                "market": market,
                "sector": sector,
                "total_found": len(results),
                "stocks": results
            }
        else:
            return {"success": False, "message": f"No stocks found in '{sector}' sector."}
            
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== AI CHATBOT (GROQ) ====================

def detect_intent_and_execute(user_message):
    """Detect user intent and execute appropriate function"""
    message_lower = user_message.lower()
    
    # Check for undervalued stocks
    if any(word in message_lower for word in ['undervalued', 'undervalue', 'cheap stock', 'value stock', 'bargain', 'low pe']):
        return "find_undervalued", find_undervalued_stocks_tool()
    
    # Check for growth stocks
    elif any(word in message_lower for word in ['high growth', 'growth stock', 'fast growing', 'growing fast']):
        return "find_growth", find_high_growth_stocks_tool()
    
    # Check for dividend stocks
    elif any(word in message_lower for word in ['dividend', 'dividends', 'income stock', 'yield']):
        return "find_dividend", find_dividend_stocks_tool()
    
    # Check for comparison
    elif any(word in message_lower for word in ['compare', 'comparison', 'versus', ' vs ', ' vs.']):
        tickers = re.findall(r'\b([A-Z]{2,5})\b', user_message)
        common_words = ['PE', 'ROE', 'ROA', 'EPS', 'CEO', 'CFO', 'IPO', 'ETF', 'NSE', 'BSE', 'NYSE', 'USD', 'INR', 'THE', 'AND', 'FOR', 'VS']
        tickers = [t for t in tickers if t not in common_words]
        if len(tickers) >= 2:
            return "compare", compare_companies_tool(','.join(tickers[:5]))
    
    # Check for sector queries
    sectors = {
        'technology': 'Technology', 'tech': 'Technology', 'it': 'Technology', 'software': 'Technology',
        'healthcare': 'Healthcare', 'health': 'Healthcare', 'pharma': 'Healthcare',
        'financial': 'Financial', 'finance': 'Financial', 'bank': 'Financial', 'banking': 'Financial',
        'energy': 'Energy', 'oil': 'Energy', 'gas': 'Energy', 'power': 'Energy',
        'consumer': 'Consumer', 'retail': 'Consumer', 'fmcg': 'Consumer',
        'industrial': 'Industrial', 'auto': 'Automobile', 'automobile': 'Automobile',
        'metal': 'Metal', 'steel': 'Metal', 'cement': 'Cement', 'construction': 'Construction',
        'telecom': 'Communication', 'communication': 'Communication',
        'real estate': 'Real Estate', 'realty': 'Real Estate'
    }
    
    for key, sector in sectors.items():
        if key in message_lower and any(word in message_lower for word in ['sector', 'stocks', 'companies', 'show', 'list', 'find']):
            return "sector", get_sector_stocks_tool(sector)
    
    # Check for company analysis
    if any(word in message_lower for word in ['analyze', 'analysis', 'tell me about', 'look at', 'check', 'how is', 'what about', 'details', 'info']):
        tickers = re.findall(r'\b([A-Z]{2,5})\b', user_message)
        common_words = ['PE', 'ROE', 'ROA', 'EPS', 'CEO', 'CFO', 'IPO', 'ETF', 'NSE', 'BSE', 'NYSE', 'USD', 'INR', 'THE', 'AND', 'FOR', 'OK', 'AI']
        tickers = [t for t in tickers if t not in common_words]
        if tickers:
            return "analyze", analyze_company_tool(tickers[0])
    
    # Check for standalone ticker
    tickers = re.findall(r'\b([A-Z]{2,5})\b', user_message)
    common_words = ['PE', 'ROE', 'ROA', 'EPS', 'CEO', 'CFO', 'IPO', 'ETF', 'NSE', 'BSE', 'NYSE', 'USD', 'INR', 'THE', 'AND', 'FOR', 'CAN', 'YOU', 'HI', 'HELLO', 'OK', 'AI', 'IS', 'IT', 'BE', 'TO', 'IN']
    
    # Check US stocks
    us_tickers = [t for t in tickers if t not in common_words and t in US_STOCKS]
    if us_tickers:
        return "analyze", analyze_company_tool(us_tickers[0])
    
    # Check Indian stocks (without .NS)
    indian_names = [t.replace('.NS', '') for t in INDIAN_STOCKS]
    indian_tickers = [t for t in tickers if t not in common_words and t in indian_names]
    if indian_tickers:
        return "analyze", analyze_company_tool(indian_tickers[0])
    
    return None, None


def process_chatbot_message(user_message, conversation_history):
    """Process user messages with Groq AI"""
    
    api_key = None
    try:
        if hasattr(st, 'secrets') and "GROQ_API_KEY" in st.secrets:
            api_key = st.secrets["GROQ_API_KEY"]
    except:
        pass
    
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
    
    if not api_key:
        return "⚠️ Please set your GROQ_API_KEY in Streamlit Secrets."
    
    client = Groq(api_key=api_key)
    
    # Detect intent and execute
    intent, data = detect_intent_and_execute(user_message)
    
    market = st.session_state.market
    currency = '₹ (INR)' if market == 'India' else '$ (USD)'
    
    system_prompt = f"""You are a professional stock market analyst covering both US and Indian markets.

Current market focus: {market}
Currency: {currency}

Your expertise:
- Fundamental analysis (PE, ROE, margins, debt ratios)
- Company analysis and comparisons
- Finding undervalued and growth stocks

Guidelines:
- Use markdown tables for comparisons
- Highlight key metrics
- Note both strengths and risks
- Always mention this is educational, not financial advice
- Format Indian numbers appropriately (Lakhs, Crores)
- Format US numbers (Millions, Billions, Trillions)"""

    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in conversation_history[-4:]:
        if msg["role"] in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    if data:
        data_str = json.dumps(data, indent=2, default=str)
        if len(data_str) > 8000:
            data_str = data_str[:8000] + "\n... (truncated)"
        
        user_content = f"""User asked: "{user_message}"

Market: {market}
Live stock data:

{data_str}

Analyze and provide clear insights."""
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": user_message})
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=2048,
            temperature=0.7
        )
        
        return response.choices[0].message.content if response.choices[0].message.content else "I couldn't generate a response."
        
    except Exception as e:
        error_msg = str(e)
        if "rate_limit" in error_msg.lower():
            return "⚠️ Rate limit reached. Please wait a moment and try again."
        return f"❌ Error: {error_msg}"


# ==================== STREAMLIT UI ====================

# Header
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.title("📊 AI Stock Analyzer")
    st.markdown("*US & Indian Markets | Live Data from Yahoo Finance*")
with col2:
    # Market selector
    market_options = ['US', 'India']
    selected_market = st.selectbox(
        "🌍 Market",
        market_options,
        index=market_options.index(st.session_state.market),
        key="market_selector"
    )
    if selected_market != st.session_state.market:
        st.session_state.market = selected_market
        st.session_state.chat_messages = []
        st.cache_data.clear()
        st.rerun()
with col3:
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Market indicator
market_emoji = "🇺🇸" if st.session_state.market == 'US' else "🇮🇳"
st.info(f"{market_emoji} Currently viewing **{st.session_state.market}** market stocks")

st.markdown("---")

# Check API key
api_key = None
try:
    if hasattr(st, 'secrets') and "GROQ_API_KEY" in st.secrets:
        api_key = st.secrets["GROQ_API_KEY"]
except:
    pass

if not api_key:
    api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    st.error("⚠️ **Groq API Key not found!**")
    st.markdown("""
    **Setup:**
    1. Get FREE API key: https://console.groq.com/keys
    2. Add to Streamlit Secrets:
    ```
    GROQ_API_KEY = "gsk_your_key_here"
    ```
    """)
    st.stop()

# Quick Actions
st.markdown("### ⚡ Quick Actions")

if st.session_state.market == 'India':
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🔍 Undervalued", use_container_width=True, key="btn_undervalued"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find undervalued Indian stocks with low PE"})
            st.rerun()
    with col2:
        if st.button("📈 Growth", use_container_width=True, key="btn_growth"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find high growth Indian stocks"})
            st.rerun()
    with col3:
        if st.button("💰 Dividends", use_container_width=True, key="btn_dividend"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find Indian dividend stocks"})
            st.rerun()
    with col4:
        if st.button("🏢 Analyze TCS", use_container_width=True, key="btn_tcs"):
            st.session_state.chat_messages.append({"role": "user", "content": "Analyze TCS stock"})
            st.rerun()
    with col5:
        if st.button("🧹 Clear", use_container_width=True, key="btn_clear"):
            st.session_state.chat_messages = []
            st.rerun()
else:
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🔍 Undervalued", use_container_width=True, key="btn_undervalued"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find undervalued stocks with low PE"})
            st.rerun()
    with col2:
        if st.button("📈 Growth", use_container_width=True, key="btn_growth"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find high growth stocks"})
            st.rerun()
    with col3:
        if st.button("💰 Dividends", use_container_width=True, key="btn_dividend"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find dividend stocks"})
            st.rerun()
    with col4:
        if st.button("🏢 Analyze AAPL", use_container_width=True, key="btn_aapl"):
            st.session_state.chat_messages.append({"role": "user", "content": "Analyze AAPL stock"})
            st.rerun()
    with col5:
        if st.button("🧹 Clear", use_container_width=True, key="btn_clear"):
            st.session_state.chat_messages = []
            st.rerun()

st.markdown("---")

# Chat Display
for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input(f"Ask about {'Indian' if st.session_state.market == 'India' else 'US'} stocks..."):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("🔍 Fetching live data..."):
            response = process_chatbot_message(prompt, st.session_state.chat_messages[:-1])
        st.markdown(response)
    
    st.session_state.chat_messages.append({"role": "assistant", "content": response})
    st.rerun()

# Help section
if len(st.session_state.chat_messages) == 0:
    st.markdown("### 💡 What can I help you with?")
    
    if st.session_state.market == 'India':
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **📊 Stock Screening (India)**
            - "Find undervalued stocks"
            - "Show high growth stocks"
            - "Find dividend stocks"
            - "List IT sector stocks"
            - "Show banking stocks"
            """)
        with col2:
            st.markdown("""
            **🔍 Stock Analysis (India)**
            - "Analyze TCS"
            - "Tell me about RELIANCE"
            - "Compare INFY, TCS, WIPRO"
            - "How is HDFC Bank doing?"
            - "Check TATAMOTORS"
            """)
        
        st.info("💡 **Popular Indian Stocks:** RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, BHARTIARTL, ITC, HINDUNILVR, MARUTI")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **📊 Stock Screening (US)**
            - "Find undervalued stocks"
            - "Show high growth stocks"
            - "Find dividend stocks"
            - "List technology stocks"
            """)
        with col2:
            st.markdown("""
            **🔍 Stock Analysis (US)**
            - "Analyze AAPL"
            - "Tell me about NVDA"
            - "Compare MSFT, GOOGL, AMZN"
            - "How is Tesla doing?"
            """)
        
        st.info("💡 **Popular US Stocks:** AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, JPM, V, JNJ")

# Footer
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; color: #888;'>
    <p><strong>AI Stock Analyzer</strong> | {market_emoji} {st.session_state.market} Market | Powered by Yahoo Finance + Groq AI</p>
    <p style='font-size: 0.8rem;'>⚠️ For educational purposes only. Not financial advice. Always do your own research.</p>
</div>
""", unsafe_allow_html=True)
