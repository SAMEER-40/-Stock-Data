"""
Configuration management for Stock Data Platform.

All configurable values are centralized here with sensible defaults.
No magic numbers in application code.
"""
from pathlib import Path
from typing import List, Tuple

# === Paths ===
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "stock_data.db"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# === Database ===
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# === Stock Configuration ===
# 12 major Indian NSE stocks for optimal speed/coverage balance
INDIAN_STOCKS: List[Tuple[str, str, str]] = [
    ("RELIANCE.NS", "Reliance Industries", "Energy"),
    ("TCS.NS", "Tata Consultancy Services", "IT"),
    ("HDFCBANK.NS", "HDFC Bank", "Banking"),
    ("INFY.NS", "Infosys", "IT"),
    ("ICICIBANK.NS", "ICICI Bank", "Banking"),
    ("HINDUNILVR.NS", "Hindustan Unilever", "FMCG"),
    ("SBIN.NS", "State Bank of India", "Banking"),
    ("BHARTIARTL.NS", "Bharti Airtel", "Telecom"),
    ("ITC.NS", "ITC Limited", "FMCG"),
    ("KOTAKBANK.NS", "Kotak Mahindra Bank", "Banking"),
    ("LT.NS", "Larsen & Toubro", "Infrastructure"),
    ("TATAMOTORS.NS", "Tata Motors", "Automobile"),
]

# === Data Ingestion ===
# Historical data window (2 years = ~500 trading days)
HISTORY_PERIOD = "2y"

# Retry configuration for API failures
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0

# === Analytics Parameters ===
# Rolling window sizes (in trading days)
MA_WINDOW_7 = 7
MA_WINDOW_20 = 20
VOLATILITY_WINDOW = 20
RSI_WINDOW = 14
WEEK_52_WINDOW = 252  # Approximate trading days in a year

# === API Configuration ===
API_TITLE = "Stock Data Intelligence Platform"
API_DESCRIPTION = """
Production-grade REST API for Indian equity analysis.

## Features
- Real-time stock data from NSE via yfinance
- Pre-computed analytics: Moving averages, Volatility, RSI
- 52-week high/low statistics
- Stock comparison and correlation analysis
"""
API_VERSION = "1.0.0"

# Default query limits
DEFAULT_DAYS = 30
MAX_DAYS = 365
