import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv
import re

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
    
    /* Headers - always white */
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        font-weight: 600 !important;
    }
    
    /* All text - light gray */
    p, span, div, label, .stMarkdown {
        color: #e5e7eb !important;
    }
    
    /* Chat input */
    .stChatFloatingInputContainer {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
    }
    
    /* Chat messages */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        margin: 0.5rem 0 !important;
        color: #ffffff !important;
    }
    
    /* Input fields */
    input, textarea, .stTextInput input, .stTextArea textarea {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    
    /* Buttons */
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
    
    /* Metrics */
    .stMetric {
        background: rgba(255, 255, 255, 0.05) !important;
        padding: 1rem !important;
        border-radius: 8px !important;
    }
    
    .stMetric label {
        color: #9ca3af !important;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        color: #ffffff !important;
    }
    
    /* Dataframes/Tables */
    .stDataFrame, table {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #ffffff !important;
    }
    
    .stDataFrame th {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
    }
    
    .stDataFrame td {
        color: #e5e7eb !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #ffffff !important;
    }
    
    /* Success/Info/Warning/Error boxes */
    .stSuccess, .stInfo, .stWarning, .stError {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
    }
    
    /* Sidebar (if you add one later) */
    .css-1d391kg, .st-emotion-cache-1cypcdb {
        background: #1e293b !important;
    }
    
    /* Links */
    a {
        color: #60a5fa !important;
    }
    
    a:hover {
        color: #93c5fd !important;
    }
    
    /* Code blocks */
    code {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #fbbf24 !important;
        padding: 0.2rem 0.4rem !important;
        border-radius: 4px !important;
    }
    
    pre {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #e5e7eb !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
</style>
""", unsafe_allow_html=True)

# Stock Universe
SP500_MAJOR = [
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

# Session state
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'show_settings' not in st.session_state:
    st.session_state.show_settings = False

# ==================== FUNDAMENTAL ANALYSIS FUNCTIONS ====================

@st.cache_data(ttl=3600)
def get_stock_fundamentals(ticker):
    """Get comprehensive fundamental data"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period='2y')
        
        if hist.empty:
            return None
        
        current_price = hist['Close'].iloc[-1]
        
        # Calculate growth metrics
        revenue_growth = None
        earnings_growth = None
        
        try:
            financials = stock.financials
            if financials is not None and not financials.empty and len(financials.columns) >= 2:
                if 'Total Revenue' in financials.index:
                    recent_rev = financials.loc['Total Revenue'].iloc[0]
                    old_rev = financials.loc['Total Revenue'].iloc[-1]
                    revenue_growth = ((recent_rev - old_rev) / abs(old_rev)) * 100
                
                if 'Net Income' in financials.index:
                    recent_earn = financials.loc['Net Income'].iloc[0]
                    old_earn = financials.loc['Net Income'].iloc[-1]
                    if old_earn != 0:
                        earnings_growth = ((recent_earn - old_earn) / abs(old_earn)) * 100
        except:
            pass
        
        fundamentals = {
            "ticker": ticker,
            "name": info.get('longName', ticker),
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "market_cap": info.get('marketCap', 0),
            "price": round(current_price, 2),
            
            # Valuation
            "pe_ratio": info.get('trailingPE'),
            "forward_pe": info.get('forwardPE'),
            "peg_ratio": info.get('pegRatio'),
            "price_to_book": info.get('priceToBook'),
            "price_to_sales": info.get('priceToSalesTrailing12Months'),
            "ev_to_revenue": info.get('enterpriseToRevenue'),
            "ev_to_ebitda": info.get('enterpriseToEbitda'),
            
            # Profitability
            "profit_margin": info.get('profitMargins'),
            "operating_margin": info.get('operatingMargins'),
            "roe": info.get('returnOnEquity'),
            "roa": info.get('returnOnAssets'),
            "roic": info.get('returnOnCapital'),
            
            # Financial Health
            "debt_to_equity": info.get('debtToEquity'),
            "current_ratio": info.get('currentRatio'),
            "quick_ratio": info.get('quickRatio'),
            "total_debt": info.get('totalDebt'),
            "total_cash": info.get('totalCash'),
            
            # Growth
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "revenue_per_share": info.get('revenuePerShare'),
            "earnings_per_share": info.get('trailingEps'),
            
            # Dividends
            "dividend_yield": info.get('dividendYield'),
            "payout_ratio": info.get('payoutRatio'),
            "dividend_rate": info.get('dividendRate'),
            
            # Other
            "beta": info.get('beta'),
            "52_week_high": info.get('fiftyTwoWeekHigh'),
            "52_week_low": info.get('fiftyTwoWeekLow'),
            "avg_volume": info.get('averageVolume'),
            "float_shares": info.get('floatShares'),
            "shares_outstanding": info.get('sharesOutstanding'),
            
            # Description
            "business_summary": info.get('longBusinessSummary', 'N/A')
        }
        
        return fundamentals
        
    except Exception as e:
        return None

def fundamental_screener_tool(
    min_market_cap=None, max_market_cap=None,
    min_pe=None, max_pe=None,
    min_roe=None, max_roe=None,
    min_profit_margin=None,
    max_debt_equity=None,
    min_dividend_yield=None,
    sector=None,
    min_revenue_growth=None,
    max_peg=None
):
    """Screen stocks by fundamental criteria"""
    try:
        results = []
        progress = st.empty()
        
        stocks_to_scan = SP500_MAJOR
        
        for idx, ticker in enumerate(stocks_to_scan):
            progress.text(f"Screening {ticker}... ({idx+1}/{len(stocks_to_scan)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            # Apply filters
            passes = True
            
            # Market Cap
            if min_market_cap and (not fundamentals['market_cap'] or fundamentals['market_cap'] < min_market_cap):
                passes = False
            if max_market_cap and (not fundamentals['market_cap'] or fundamentals['market_cap'] > max_market_cap):
                passes = False
            
            # PE Ratio
            if min_pe and (not fundamentals['pe_ratio'] or fundamentals['pe_ratio'] < min_pe):
                passes = False
            if max_pe and (not fundamentals['pe_ratio'] or fundamentals['pe_ratio'] > max_pe):
                passes = False
            
            # ROE
            if min_roe and (not fundamentals['roe'] or fundamentals['roe'] * 100 < min_roe):
                passes = False
            if max_roe and (not fundamentals['roe'] or fundamentals['roe'] * 100 > max_roe):
                passes = False
            
            # Profit Margin
            if min_profit_margin and (not fundamentals['profit_margin'] or fundamentals['profit_margin'] * 100 < min_profit_margin):
                passes = False
            
            # Debt to Equity
            if max_debt_equity and (fundamentals['debt_to_equity'] and fundamentals['debt_to_equity'] > max_debt_equity):
                passes = False
            
            # Dividend Yield
            if min_dividend_yield and (not fundamentals['dividend_yield'] or fundamentals['dividend_yield'] * 100 < min_dividend_yield):
                passes = False
            
            # Sector
            if sector and fundamentals['sector'] != sector:
                passes = False
            
            # Revenue Growth
            if min_revenue_growth and (not fundamentals['revenue_growth'] or fundamentals['revenue_growth'] < min_revenue_growth):
                passes = False
            
            # PEG Ratio
            if max_peg and (not fundamentals['peg_ratio'] or fundamentals['peg_ratio'] > max_peg):
                passes = False
            
            if passes:
                results.append({
                    "ticker": fundamentals['ticker'],
                    "name": fundamentals['name'],
                    "price": fundamentals['price'],
                    "market_cap": fundamentals['market_cap'],
                    "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else None,
                    "roe": round(fundamentals['roe'] * 100, 2) if fundamentals['roe'] else None,
                    "profit_margin": round(fundamentals['profit_margin'] * 100, 2) if fundamentals['profit_margin'] else None,
                    "debt_to_equity": round(fundamentals['debt_to_equity'], 2) if fundamentals['debt_to_equity'] else None,
                    "dividend_yield": round(fundamentals['dividend_yield'] * 100, 2) if fundamentals['dividend_yield'] else None,
                    "sector": fundamentals['sector'],
                    "peg_ratio": round(fundamentals['peg_ratio'], 2) if fundamentals['peg_ratio'] else None
                })
        
        progress.empty()
        
        if results:
            return {
                "success": True,
                "total_found": len(results),
                "stocks": results[:30]
            }
        else:
            return {
                "success": False,
                "message": "No stocks found matching criteria"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def analyze_company_tool(ticker):
    """Deep dive analysis of a company"""
    try:
        fundamentals = get_stock_fundamentals(ticker)
        
        if not fundamentals:
            return {"success": False, "error": f"Could not fetch data for {ticker}"}
        
        # Calculate valuation score
        valuation_score = 0
        
        if fundamentals['pe_ratio']:
            if fundamentals['pe_ratio'] < 15:
                valuation_score += 2
            elif fundamentals['pe_ratio'] < 25:
                valuation_score += 1
        
        if fundamentals['peg_ratio']:
            if fundamentals['peg_ratio'] < 1:
                valuation_score += 2
            elif fundamentals['peg_ratio'] < 2:
                valuation_score += 1
        
        if fundamentals['price_to_book']:
            if fundamentals['price_to_book'] < 3:
                valuation_score += 1
        
        # Calculate profitability score
        profitability_score = 0
        
        if fundamentals['roe']:
            if fundamentals['roe'] > 0.20:
                profitability_score += 2
            elif fundamentals['roe'] > 0.15:
                profitability_score += 1
        
        if fundamentals['profit_margin']:
            if fundamentals['profit_margin'] > 0.20:
                profitability_score += 2
            elif fundamentals['profit_margin'] > 0.10:
                profitability_score += 1
        
        if fundamentals['operating_margin']:
            if fundamentals['operating_margin'] > 0.20:
                profitability_score += 1
        
        # Calculate financial health score
        health_score = 0
        
        if fundamentals['current_ratio']:
            if fundamentals['current_ratio'] > 2:
                health_score += 2
            elif fundamentals['current_ratio'] > 1.5:
                health_score += 1
        
        if fundamentals['debt_to_equity']:
            if fundamentals['debt_to_equity'] < 0.5:
                health_score += 2
            elif fundamentals['debt_to_equity'] < 1.0:
                health_score += 1
        
        # Calculate growth score
        growth_score = 0
        
        if fundamentals['revenue_growth']:
            if fundamentals['revenue_growth'] > 20:
                growth_score += 2
            elif fundamentals['revenue_growth'] > 10:
                growth_score += 1
        
        if fundamentals['earnings_growth']:
            if fundamentals['earnings_growth'] > 20:
                growth_score += 2
            elif fundamentals['earnings_growth'] > 10:
                growth_score += 1
        
        # Overall score
        overall_score = valuation_score + profitability_score + health_score + growth_score
        max_score = 18
        overall_rating = (overall_score / max_score) * 100
        
        return {
            "success": True,
            "company": {
                "ticker": fundamentals['ticker'],
                "name": fundamentals['name'],
                "sector": fundamentals['sector'],
                "industry": fundamentals['industry'],
                "price": fundamentals['price'],
                "market_cap": fundamentals['market_cap']
            },
            "valuation": {
                "pe_ratio": fundamentals['pe_ratio'],
                "forward_pe": fundamentals['forward_pe'],
                "peg_ratio": fundamentals['peg_ratio'],
                "price_to_book": fundamentals['price_to_book'],
                "price_to_sales": fundamentals['price_to_sales'],
                "score": valuation_score
            },
            "profitability": {
                "roe": round(fundamentals['roe'] * 100, 2) if fundamentals['roe'] else None,
                "roa": round(fundamentals['roa'] * 100, 2) if fundamentals['roa'] else None,
                "profit_margin": round(fundamentals['profit_margin'] * 100, 2) if fundamentals['profit_margin'] else None,
                "operating_margin": round(fundamentals['operating_margin'] * 100, 2) if fundamentals['operating_margin'] else None,
                "score": profitability_score
            },
            "financial_health": {
                "debt_to_equity": fundamentals['debt_to_equity'],
                "current_ratio": fundamentals['current_ratio'],
                "quick_ratio": fundamentals['quick_ratio'],
                "total_debt": fundamentals['total_debt'],
                "total_cash": fundamentals['total_cash'],
                "score": health_score
            },
            "growth": {
                "revenue_growth": fundamentals['revenue_growth'],
                "earnings_growth": fundamentals['earnings_growth'],
                "score": growth_score
            },
            "dividends": {
                "dividend_yield": round(fundamentals['dividend_yield'] * 100, 2) if fundamentals['dividend_yield'] else None,
                "payout_ratio": round(fundamentals['payout_ratio'] * 100, 2) if fundamentals['payout_ratio'] else None,
                "dividend_rate": fundamentals['dividend_rate']
            },
            "rating": {
                "overall_score": overall_score,
                "max_score": max_score,
                "percentage": round(overall_rating, 1)
            },
            "business_summary": fundamentals['business_summary']
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def compare_companies_tool(tickers):
    """Compare multiple companies side-by-side"""
    try:
        if isinstance(tickers, str):
            tickers = [t.strip().upper() for t in tickers.split(',')]
        
        comparisons = []
        
        for ticker in tickers[:5]:  # Limit to 5 companies
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                comparisons.append({
                    "ticker": ticker,
                    "error": "Could not fetch data"
                })
                continue
            
            comparisons.append({
                "ticker": ticker,
                "name": fundamentals['name'],
                "price": fundamentals['price'],
                "market_cap": fundamentals['market_cap'],
                "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else None,
                "peg_ratio": round(fundamentals['peg_ratio'], 2) if fundamentals['peg_ratio'] else None,
                "roe": round(fundamentals['roe'] * 100, 2) if fundamentals['roe'] else None,
                "profit_margin": round(fundamentals['profit_margin'] * 100, 2) if fundamentals['profit_margin'] else None,
                "debt_to_equity": round(fundamentals['debt_to_equity'], 2) if fundamentals['debt_to_equity'] else None,
                "dividend_yield": round(fundamentals['dividend_yield'] * 100, 2) if fundamentals['dividend_yield'] else None,
                "revenue_growth": round(fundamentals['revenue_growth'], 2) if fundamentals['revenue_growth'] else None,
                "sector": fundamentals['sector']
            })
        
        return {
            "success": True,
            "comparisons": comparisons
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_undervalued_stocks_tool(max_pe=15, min_roe=15, max_peg=1.5):
    """Find undervalued stocks with good fundamentals"""
    try:
        results = []
        progress = st.empty()
        
        for idx, ticker in enumerate(SP500_MAJOR):
            progress.text(f"Scanning {ticker}... ({idx+1}/{len(SP500_MAJOR)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            pe = fundamentals['pe_ratio']
            roe = fundamentals['roe']
            peg = fundamentals['peg_ratio']
            
            # Undervalued criteria
            if pe and roe and peg:
                if pe < max_pe and roe * 100 > min_roe and peg < max_peg:
                    results.append({
                        "ticker": ticker,
                        "name": fundamentals['name'],
                        "price": fundamentals['price'],
                        "pe_ratio": round(pe, 2),
                        "peg_ratio": round(peg, 2),
                        "roe": round(roe * 100, 2),
                        "sector": fundamentals['sector'],
                        "profit_margin": round(fundamentals['profit_margin'] * 100, 2) if fundamentals['profit_margin'] else None
                    })
        
        progress.empty()
        
        if results:
            # Sort by PEG ratio (lower is better)
            results = sorted(results, key=lambda x: x['peg_ratio'])
            return {
                "success": True,
                "total_found": len(results),
                "stocks": results[:20]
            }
        else:
            return {
                "success": False,
                "message": "No undervalued stocks found"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_high_growth_stocks_tool(min_revenue_growth=20, min_roe=15):
    """Find high growth stocks"""
    try:
        results = []
        progress = st.empty()
        
        for idx, ticker in enumerate(SP500_MAJOR):
            progress.text(f"Scanning {ticker}... ({idx+1}/{len(SP500_MAJOR)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            rev_growth = fundamentals['revenue_growth']
            roe = fundamentals['roe']
            
            if rev_growth and roe:
                if rev_growth > min_revenue_growth and roe * 100 > min_roe:
                    results.append({
                        "ticker": ticker,
                        "name": fundamentals['name'],
                        "price": fundamentals['price'],
                        "revenue_growth": round(rev_growth, 2),
                        "roe": round(roe * 100, 2),
                        "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else None,
                        "sector": fundamentals['sector']
                    })
        
        progress.empty()
        
        if results:
            # Sort by revenue growth
            results = sorted(results, key=lambda x: x['revenue_growth'], reverse=True)
            return {
                "success": True,
                "total_found": len(results),
                "stocks": results[:20]
            }
        else:
            return {
                "success": False,
                "message": "No high growth stocks found"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_dividend_stocks_tool(min_yield=3, max_payout_ratio=60):
    """Find high dividend yield stocks"""
    try:
        results = []
        progress = st.empty()
        
        for idx, ticker in enumerate(SP500_MAJOR):
            progress.text(f"Scanning {ticker}... ({idx+1}/{len(SP500_MAJOR)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            div_yield = fundamentals['dividend_yield']
            payout = fundamentals['payout_ratio']
            
            if div_yield:
                yield_pct = div_yield * 100
                if yield_pct > min_yield:
                    if not max_payout_ratio or not payout or payout * 100 < max_payout_ratio:
                        results.append({
                            "ticker": ticker,
                            "name": fundamentals['name'],
                            "price": fundamentals['price'],
                            "dividend_yield": round(yield_pct, 2),
                            "payout_ratio": round(payout * 100, 2) if payout else None,
                            "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else None,
                            "sector": fundamentals['sector']
                        })
        
        progress.empty()
        
        if results:
            # Sort by dividend yield
            results = sorted(results, key=lambda x: x['dividend_yield'], reverse=True)
            return {
                "success": True,
                "total_found": len(results),
                "stocks": results[:20]
            }
        else:
            return {
                "success": False,
                "message": "No dividend stocks found"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_sector_stocks_tool(sector):
    """Get all stocks in a specific sector"""
    try:
        results = []
        progress = st.empty()
        
        for idx, ticker in enumerate(SP500_MAJOR):
            progress.text(f"Scanning {ticker}... ({idx+1}/{len(SP500_MAJOR)})")
            
            fundamentals = get_stock_fundamentals(ticker)
            if not fundamentals:
                continue
            
            if fundamentals['sector'].lower() == sector.lower():
                results.append({
                    "ticker": ticker,
                    "name": fundamentals['name'],
                    "price": fundamentals['price'],
                    "market_cap": fundamentals['market_cap'],
                    "pe_ratio": round(fundamentals['pe_ratio'], 2) if fundamentals['pe_ratio'] else None,
                    "roe": round(fundamentals['roe'] * 100, 2) if fundamentals['roe'] else None,
                    "industry": fundamentals['industry']
                })
        
        progress.empty()
        
        if results:
            # Sort by market cap
            results = sorted(results, key=lambda x: x['market_cap'] or 0, reverse=True)
            return {
                "success": True,
                "sector": sector,
                "total_found": len(results),
                "stocks": results
            }
        else:
            return {
                "success": False,
                "message": f"No stocks found in {sector} sector"
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==================== AI CHATBOT FUNCTION ====================

def process_chatbot_message(user_message, conversation_history):
    """Process user messages with Gemini AI"""
    
    # Try multiple ways to get the API key
    api_key = None
    
    # Method 1: Streamlit secrets
    try:
        if hasattr(st, 'secrets') and "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
            st.write("DEBUG: Loaded from Streamlit secrets")  # Temporary debug
    except Exception as e:
        st.write(f"DEBUG: Secrets error: {e}")  # Temporary debug
    
    # Method 2: Environment variable
    if not api_key:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            st.write("DEBUG: Loaded from environment")  # Temporary debug
    
    if not api_key:
        return "⚠️ Please set your GOOGLE_API_KEY in Streamlit Secrets or environment variables."
    
    genai.configure(api_key=api_key)
    
    tools = [
        genai.protos.Tool(
            function_declarations=[
                genai.protos.FunctionDeclaration(
                    name="fundamental_screener",
                    description="Screen stocks by fundamental criteria like PE ratio, ROE, profit margin, debt levels, dividend yield, sector, market cap, and growth rates. Returns matching stocks.",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "min_market_cap": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum market cap"),
                            "max_market_cap": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Maximum market cap"),
                            "min_pe": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum PE ratio"),
                            "max_pe": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Maximum PE ratio"),
                            "min_roe": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum ROE percentage"),
                            "max_roe": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Maximum ROE percentage"),
                            "min_profit_margin": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum profit margin percentage"),
                            "max_debt_equity": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Maximum debt to equity ratio"),
                            "min_dividend_yield": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum dividend yield percentage"),
                            "sector": genai.protos.Schema(type=genai.protos.Type.STRING, description="Sector to filter (e.g., Technology, Healthcare, Finance)"),
                            "min_revenue_growth": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum revenue growth percentage"),
                            "max_peg": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Maximum PEG ratio")
                        }
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="analyze_company",
                    description="Get detailed fundamental analysis of a specific company including valuation metrics, profitability scores, financial health, growth metrics, and overall rating.",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "ticker": genai.protos.Schema(type=genai.protos.Type.STRING, description="Stock ticker symbol")
                        },
                        required=["ticker"]
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="compare_companies",
                    description="Compare multiple companies side-by-side with key financial metrics",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "tickers": genai.protos.Schema(type=genai.protos.Type.STRING, description="Comma-separated ticker symbols")
                        },
                        required=["tickers"]
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="find_undervalued_stocks",
                    description="Find undervalued stocks with low PE, high ROE, and low PEG ratio",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "max_pe": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Maximum PE ratio"),
                            "min_roe": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum ROE percentage"),
                            "max_peg": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Maximum PEG ratio")
                        }
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="find_high_growth_stocks",
                    description="Find high revenue growth stocks with strong profitability",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "min_revenue_growth": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum revenue growth percentage"),
                            "min_roe": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum ROE percentage")
                        }
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="find_dividend_stocks",
                    description="Find high dividend yield stocks with sustainable payouts",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "min_yield": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Minimum dividend yield percentage"),
                            "max_payout_ratio": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Maximum payout ratio percentage")
                        }
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="get_sector_stocks",
                    description="Get all stocks in a specific sector",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "sector": genai.protos.Schema(type=genai.protos.Type.STRING, description="Sector name (Technology, Healthcare, Finance, etc.)")
                        },
                        required=["sector"]
                    )
                )
            ]
        )
    ]
    
    system_instruction = """You are a professional stock market analyst combining both fundamental and technical analysis.

Your expertise includes:
- **Fundamental Analysis**: Valuation (PE, PEG), profitability (ROE, margins), financial health (debt, cash)
- **Technical Analysis**: Swing trading setups (EMA 20 pullbacks, SMA 50 pullbacks, consolidation breakouts)
- Company comparisons and sector analysis
- Finding undervalued and high-quality investment opportunities

**Swing Trading Strategy:**
When user asks to "scan the Nasdaq" or find "trading setups," use swing trading analysis:
- EMA 20 Pullback: Stock pulls back to 20 EMA in uptrend (best setup)
- SMA 50 Pullback: Stock bounces off 50 SMA support
- Consolidation Breakout: Stock breaking out of tight range near highs
- Quality scores: 85+ (exceptional), 75-84 (strong), 65-74 (good)
- All setups include entry, stop loss (3% risk), and target prices

**Investment Analysis:**
When user asks about "fundamentals" or "value," use fundamental analysis:
- Screen by PE, ROE, profit margins, debt levels
- Find undervalued, high-growth, or dividend stocks
- Provide detailed company analysis with ratings

Communication style:
- Be professional but conversational
- Provide actionable insights
- Always emphasize: educational content, not financial advice
- Use data to support recommendations"""

    model = genai.GenerativeModel(
        'models/gemini-2.5-flash',
        tools=tools,
        system_instruction=system_instruction
    )
    
    history = []
    for msg in conversation_history:
        if msg["role"] == "user":
            history.append({"role": "user", "parts": [msg["content"]]})
        elif msg["role"] == "assistant":
            history.append({"role": "model", "parts": [msg["content"]]})
    
    chat = model.start_chat(history=history)
    
    max_iterations = 5
    iteration = 0
    
while iteration < max_iterations:
        iteration += 1
        
        try:
            # Only send user_message on first iteration
            if user_message and user_message.strip():
                response = chat.send_message(user_message)
            else:
                # Empty message, break loop
                break
            
            # Check if AI wants to use a function
            if response.candidates[0].content.parts[0].function_call:
                function_call = response.candidates[0].content.parts[0].function_call
                function_name = function_call.name
                function_args = {}
                
                for key, value in function_call.args.items():
                    function_args[key] = value
                
                # Execute functions
                if function_name == "fundamental_screener":
                    result = fundamental_screener_tool(
                        min_market_cap=function_args.get("min_market_cap"),
                        max_market_cap=function_args.get("max_market_cap"),
                        min_pe=function_args.get("min_pe"),
                        max_pe=function_args.get("max_pe"),
                        min_roe=function_args.get("min_roe"),
                        max_roe=function_args.get("max_roe"),
                        min_profit_margin=function_args.get("min_profit_margin"),
                        max_debt_equity=function_args.get("max_debt_equity"),
                        min_dividend_yield=function_args.get("min_dividend_yield"),
                        sector=function_args.get("sector"),
                        min_revenue_growth=function_args.get("min_revenue_growth"),
                        max_peg=function_args.get("max_peg")
                    )
                elif function_name == "analyze_company":
                    result = analyze_company_tool(function_args.get("ticker"))
                elif function_name == "compare_companies":
                    result = compare_companies_tool(function_args.get("tickers"))
                elif function_name == "find_undervalued_stocks":
                    result = find_undervalued_stocks_tool(
                        max_pe=function_args.get("max_pe", 15),
                        min_roe=function_args.get("min_roe", 15),
                        max_peg=function_args.get("max_peg", 1.5)
                    )
                elif function_name == "find_high_growth_stocks":
                    result = find_high_growth_stocks_tool(
                        min_revenue_growth=function_args.get("min_revenue_growth", 20),
                        min_roe=function_args.get("min_roe", 15)
                    )
                elif function_name == "find_dividend_stocks":
                    result = find_dividend_stocks_tool(
                        min_yield=function_args.get("min_yield", 3),
                        max_payout_ratio=function_args.get("max_payout_ratio", 60)
                    )
                elif function_name == "get_sector_stocks":
                    result = get_sector_stocks_tool(function_args.get("sector"))
                else:
                    result = {"error": f"Unknown function: {function_name}"}
                
                # Send function response back to AI
                response = chat.send_message(
                    genai.protos.Content(
                        parts=[
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=function_name,
                                    response={"result": result}
                                )
                            )
                        ]
                    )
                )
                
                # Clear user_message so we don't resend it
                user_message = None
                
                # Check if we got a text response now
                if response.text and response.text.strip():
                    return response.text
                
                # Otherwise continue loop (might call another function)
                continue
            
            # No function call - return the text response
            if response.text and response.text.strip():
                return response.text
            else:
                return "I apologize, but I couldn't generate a response. Please try rephrasing your question."
            
        except Exception as e:
            error_msg = str(e)
            if "empty" in error_msg.lower():
                return "I encountered an issue processing your request. Please try asking in a different way."
            return f"❌ Error: {error_msg}"
    
        return "⚠️ Response took too long. Please try a simpler question."
 # Get response text
        response_text = response.text if response.text else "I apologize, but I couldn't generate a response. Please try rephrasing your question."
        return response_text
            
        except Exception as e:
            return f"❌ Error: {str(e)}\n\nPlease try asking in a different way."
    
    return "⚠️ Response took too long. Please try a simpler question."

# ==================== UI ====================

col1, col2 = st.columns([4, 1])
with col1:
    st.title("📊 AI Stock Analyzer")
    st.markdown("*Fundamental analysis powered by Google Gemini")
with col2:
    if st.button("⚙️ Settings", use_container_width=True):
        st.session_state.show_settings = not st.session_state.show_settings

st.markdown("---")

# Check API key
# Check API key
api_key = None

try:
    if hasattr(st, 'secrets') and "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
except:
    pass

if not api_key:
    api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    st.error("⚠️ **Google API Key not found!**")
    st.markdown("""
    **Setup:**
    
    1. Get FREE API key: https://aistudio.google.com/app/apikey
    2. Add to Streamlit Secrets (Settings → Secrets):
```
    GOOGLE_API_KEY = "your-key-here"
```
    """)
    st.stop()
if not api_key:
    st.error("⚠️ **Google API Key not found!**")
    st.markdown("""
    **Setup:**
    
    1. Get FREE API key: https://aistudio.google.com/app/apikey
    2. Add to Streamlit Secrets (Settings → Secrets):
```
    GOOGLE_API_KEY = "your-key-here"
```
    """)
    st.stop()


# Quick actions
st.markdown("### ⚡ Quick Actions")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("🔍 Find Undervalued", use_container_width=True):
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "Find undervalued stocks with good fundamentals"
        })
        st.rerun()

with col2:
    if st.button("📈 High Growth", use_container_width=True):
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "Find high growth stocks"
        })
        st.rerun()

with col3:
    if st.button("💰 Dividend Stocks", use_container_width=True):
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "Find high dividend yield stocks"
        })
        st.rerun()

with col4:
    if st.button("🏢 Analyze Company", use_container_width=True):
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "Analyze AAPL in detail"
        })
        st.rerun()

with col5:
    if st.button("🧹 Clear", use_container_width=True):
        st.session_state.chat_messages = []
        st.rerun()

st.markdown("---")

# Chat display
for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about stocks, companies, sectors, or request stock screens..."):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = process_chatbot_message(prompt, st.session_state.chat_messages[:-1])
        st.markdown(response)
    
    st.session_state.chat_messages.append({"role": "assistant", "content": response})
    st.rerun()

# Examples
if len(st.session_state.chat_messages) == 0:
    st.markdown("### 💡 Try asking:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Screening:**
        - "Find stocks with PE < 15 and ROE > 20%"
        - "Show me technology stocks with low debt"
        - "Find undervalued stocks in healthcare sector"
        - "Which stocks have dividend yield above 4%?"
        """)
    
    with col2:
        st.markdown("""
        **Analysis:**
        - "Analyze Apple in detail"
        - "Compare MSFT, GOOGL, and AAPL"
        - "What are the best tech stocks to buy?"
        - "Find profitable companies with high growth"
        """)

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888;'>
    <p><strong>AI Stock Analyzer</strong> | Powered by Google Gemini</p>
    <p style='font-size: 0.85rem;'>⚠️ Educational content. Not financial advice.</p>
</div>
""", unsafe_allow_html=True)
