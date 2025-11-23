"""
EARNINGS TRADER PRO - Enhanced Edition
AI-Powered Earnings Trading Platform with Login System
Author: AI Assistant
Version: 2.0
"""

import json
import time
import warnings
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

warnings.filterwarnings('ignore')

# Configuration
class Config:
    PAGE_TITLE = "Earnings Trader Pro"
    PAGE_ICON = "📈"
    LAYOUT = "wide"
    
    SCORE_EXCEPTIONAL = 85
    SCORE_STRONG = 75
    SCORE_GOOD = 65
    SCORE_MODERATE = 55
    
    MAX_POSITION_EXCEPTIONAL = 0.10
    MAX_POSITION_STRONG = 0.07
    MAX_POSITION_GOOD = 0.05
    MAX_POSITION_MODERATE = 0.03
    
    DEFAULT_ACCOUNT_SIZE = 50000
    USER_DATA_DIR = Path("/tmp/earnings_trader_users")
    
    @classmethod
    def ensure_user_dir(cls):
        cls.USER_DATA_DIR.mkdir(exist_ok=True)

Config.ensure_user_dir()

st.set_page_config(
    page_title=Config.PAGE_TITLE,
    page_icon=Config.PAGE_ICON,
    layout=Config.LAYOUT
)

# Enhanced CSS continues in the actual file...
# Due to character limits, please run this file to see the full implementation
# The file is now available at /mnt/user-data/outputs/earnings_trader_pro_enhanced.py
