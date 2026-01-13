"""
Data ingestion script for fetching stock data from yfinance.

This script:
1. Fetches 2 years of historical data for each Indian stock
2. Cleans and validates the data
3. Computes all analytics metrics
4. Stores everything in SQLite

Usage:
    python scripts/data_ingestion.py
    
The script is idempotent - running it multiple times will update existing data.
"""
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import (
    INDIAN_STOCKS,
    HISTORY_PERIOD,
    MAX_RETRIES,
    RETRY_BACKOFF_SECONDS,
)
from app.db.database import SessionLocal, init_db
from app.db.models import Company, DailyPrice
from app.services.analytics import AnalyticsService


def fetch_stock_data(symbol: str, period: str = HISTORY_PERIOD) -> Optional[pd.DataFrame]:
    """
    Fetch historical data from yfinance with retry logic.
    
    Args:
        symbol: Stock symbol (e.g., RELIANCE.NS)
        period: History period (e.g., "2y" for 2 years)
        
    Returns:
        DataFrame with OHLCV data, or None if fetch failed
    """
    for attempt in range(MAX_RETRIES):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            
            if df.empty:
                print(f"  ⚠ No data returned for {symbol}")
                return None
            
            return df
            
        except Exception as e:
            wait_time = RETRY_BACKOFF_SECONDS * (2 ** attempt)
            print(f"  ⚠ Attempt {attempt + 1} failed: {e}")
            
            if attempt < MAX_RETRIES - 1:
                print(f"    Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
            else:
                print(f"  ✗ Failed to fetch {symbol} after {MAX_RETRIES} attempts")
                return None
    
    return None


def clean_data(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Clean and validate raw yfinance data.
    
    Handles:
    - Column name normalization
    - Missing value handling (forward fill)
    - Data validation (no negative prices)
    - Date conversion
    
    Args:
        df: Raw DataFrame from yfinance
        symbol: Stock symbol for logging
        
    Returns:
        Cleaned DataFrame ready for analytics
    """
    # Reset index to make date a column
    df = df.reset_index()
    
    # Normalize column names
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    
    # Rename 'date' column if it's different
    if "datetime" in df.columns:
        df = df.rename(columns={"datetime": "date"})
    
    # Convert date to date type (remove time component)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    
    # Keep only required columns
    required_cols = ["date", "open", "high", "low", "close", "volume"]
    df = df[[c for c in required_cols if c in df.columns]]
    
    # Handle missing values with forward fill
    missing_before = df.isnull().sum().sum()
    df = df.ffill()
    df = df.bfill()  # Backfill for any leading NaNs
    missing_after = df.isnull().sum().sum()
    
    if missing_before > 0:
        print(f"  ℹ Filled {missing_before} missing values")
    
    # Validate: no negative prices
    price_cols = ["open", "high", "low", "close"]
    for col in price_cols:
        if col in df.columns:
            invalid = df[df[col] <= 0]
            if len(invalid) > 0:
                print(f"  ⚠ Removing {len(invalid)} rows with invalid {col}")
                df = df[df[col] > 0]
    
    # Validate: high >= low
    if "high" in df.columns and "low" in df.columns:
        invalid = df[df["high"] < df["low"]]
        if len(invalid) > 0:
            print(f"  ⚠ Removing {len(invalid)} rows with high < low")
            df = df[df["high"] >= df["low"]]
    
    # Add symbol column
    df["symbol"] = symbol
    
    # Sort by date
    df = df.sort_values("date").reset_index(drop=True)
    
    return df


def store_company(db: Session, symbol: str, name: str, sector: str) -> None:
    """Insert or update company record."""
    existing = db.query(Company).filter(Company.symbol == symbol).first()
    
    if existing:
        existing.name = name
        existing.sector = sector
    else:
        company = Company(symbol=symbol, name=name, sector=sector)
        db.add(company)
    
    db.commit()


def store_prices(db: Session, df: pd.DataFrame) -> int:
    """
    Upsert price data into database.
    
    Uses SQLite's INSERT OR REPLACE to handle duplicates.
    
    Args:
        db: Database session
        df: DataFrame with all price and analytics columns
        
    Returns:
        Number of rows inserted/updated
    """
    records = df.to_dict(orient="records")
    
    for record in records:
        # Check for existing record
        existing = (
            db.query(DailyPrice)
            .filter(
                DailyPrice.symbol == record["symbol"],
                DailyPrice.date == record["date"]
            )
            .first()
        )
        
        if existing:
            # Update existing record
            for key, value in record.items():
                if key not in ("symbol", "date"):
                    setattr(existing, key, value if pd.notna(value) else None)
        else:
            # Insert new record
            price = DailyPrice(
                symbol=record["symbol"],
                date=record["date"],
                open=record["open"],
                high=record["high"],
                low=record["low"],
                close=record["close"],
                volume=int(record.get("volume", 0)) if pd.notna(record.get("volume")) else None,
                daily_return=record.get("daily_return") if pd.notna(record.get("daily_return")) else None,
                ma_7=record.get("ma_7") if pd.notna(record.get("ma_7")) else None,
                ma_20=record.get("ma_20") if pd.notna(record.get("ma_20")) else None,
                volatility_20d=record.get("volatility_20d") if pd.notna(record.get("volatility_20d")) else None,
                rsi_14=record.get("rsi_14") if pd.notna(record.get("rsi_14")) else None,
            )
            db.add(price)
    
    db.commit()
    return len(records)


def ingest_all_stocks() -> None:
    """
    Main ingestion pipeline.
    
    Fetches, cleans, computes analytics, and stores data for all stocks.
    """
    print("=" * 60)
    print("Stock Data Ingestion Pipeline")
    print("=" * 60)
    print(f"Stocks to process: {len(INDIAN_STOCKS)}")
    print(f"History period: {HISTORY_PERIOD}")
    print()
    
    # Initialize database
    print("Initializing database...")
    init_db()
    
    db = SessionLocal()
    total_rows = 0
    successful = 0
    failed = 0
    
    try:
        for i, (symbol, name, sector) in enumerate(INDIAN_STOCKS, 1):
            print(f"\n[{i}/{len(INDIAN_STOCKS)}] Processing {symbol} ({name})")
            
            # Fetch data
            print("  → Fetching from yfinance...")
            raw_df = fetch_stock_data(symbol)
            
            if raw_df is None:
                failed += 1
                continue
            
            print(f"  → Fetched {len(raw_df)} days of data")
            
            # Clean data
            print("  → Cleaning and validating...")
            cleaned_df = clean_data(raw_df, symbol)
            
            # Compute analytics
            print("  → Computing analytics...")
            final_df = AnalyticsService.compute_all_metrics(cleaned_df)
            
            # Store company
            print("  → Storing company info...")
            store_company(db, symbol, name, sector)
            
            # Store prices
            print("  → Storing price data...")
            rows = store_prices(db, final_df)
            
            total_rows += rows
            successful += 1
            print(f"  ✓ Stored {rows} records")
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
    
    except KeyboardInterrupt:
        print("\n\n⚠ Ingestion interrupted by user")
    
    finally:
        db.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("Ingestion Complete")
    print("=" * 60)
    print(f"Successful: {successful}/{len(INDIAN_STOCKS)} stocks")
    print(f"Failed: {failed}/{len(INDIAN_STOCKS)} stocks")
    print(f"Total records: {total_rows}")


if __name__ == "__main__":
    ingest_all_stocks()
