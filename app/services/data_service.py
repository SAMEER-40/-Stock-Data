"""
Data service layer for database operations.

All database queries are centralized here.
API routes should only call service methods, never raw queries.
"""
from datetime import date, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import pandas as pd

from app.db.models import Company, DailyPrice
from app.config import DEFAULT_DAYS, WEEK_52_WINDOW
from app.services.analytics import AnalyticsService
import time

# Simple in-memory cache
# Format: {key: (value, timestamp)}
_CACHE = {}
_TTL_SECONDS = 300  # 5 minutes

def _get_from_cache(key: str):
    """Retrieve value from cache if valid."""
    if key in _CACHE:
        value, timestamp = _CACHE[key]
        if time.time() - timestamp < _TTL_SECONDS:
            return value
        else:
            del _CACHE[key]
    return None

def _set_to_cache(key: str, value):
    """Store value in cache with current timestamp."""
    _CACHE[key] = (value, time.time())



class DataService:
    """
    Database query service.
    
    Provides type-safe methods for all database operations.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # === Company Operations ===
    
    def get_all_companies(self) -> List[Company]:
        """Retrieve all tracked companies (Cached)."""
        cache_key = "all_companies"
        cached = _get_from_cache(cache_key)
        if cached:
            return cached
            
        companies = self.db.query(Company).order_by(Company.symbol).all()
        _set_to_cache(cache_key, companies)
        return companies
    
    def get_company_by_symbol(self, symbol: str) -> Optional[Company]:
        """Get company by stock symbol."""
        return self.db.query(Company).filter(Company.symbol == symbol).first()
    
    def symbol_exists(self, symbol: str) -> bool:
        """Check if a symbol exists in the database."""
        return self.db.query(Company).filter(Company.symbol == symbol).count() > 0
    
    # === Price Data Operations ===
    
    def get_recent_prices(
        self, 
        symbol: str, 
        days: int = DEFAULT_DAYS
    ) -> List[DailyPrice]:
        """
        Get last N days of price data (Cached).
        """
        cache_key = f"prices_{symbol}_{days}"
        cached = _get_from_cache(cache_key)
        if cached:
            return cached

        prices = (
            self.db.query(DailyPrice)
            .filter(DailyPrice.symbol == symbol)
            .order_by(desc(DailyPrice.date))
            .limit(days)
            .all()
        )
        
        _set_to_cache(cache_key, prices)
        return prices
    
    def get_price_history(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DailyPrice]:
        """
        Get price history within date range.
        
        Args:
            symbol: Stock symbol
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
            
        Returns:
            List of DailyPrice records, sorted by date ascending
        """
        query = self.db.query(DailyPrice).filter(DailyPrice.symbol == symbol)
        
        if start_date:
            query = query.filter(DailyPrice.date >= start_date)
        if end_date:
            query = query.filter(DailyPrice.date <= end_date)
        
        return query.order_by(DailyPrice.date).all()
    
    def get_latest_price(self, symbol: str) -> Optional[DailyPrice]:
        """Get the most recent price record for a symbol."""
        return (
            self.db.query(DailyPrice)
            .filter(DailyPrice.symbol == symbol)
            .order_by(desc(DailyPrice.date))
            .first()
        )
    
    # === Summary Statistics ===
    
    def get_52_week_summary(self, symbol: str) -> Optional[dict]:
        """
        Calculate 52-week summary statistics.
        
        Returns:
            Dictionary with high_52w, low_52w, avg_close, current_price,
            volatility, rsi, change_52w_pct
        """
        # Get last 252 trading days
        prices = (
            self.db.query(DailyPrice)
            .filter(DailyPrice.symbol == symbol)
            .order_by(desc(DailyPrice.date))
            .limit(WEEK_52_WINDOW)
            .all()
        )
        
        if not prices:
            return None
        
        # Current (most recent) values
        current = prices[0]
        
        # Calculate from price list
        closes = [p.close for p in prices]
        high_52w = max(closes)
        low_52w = min(closes)
        avg_close = sum(closes) / len(closes)
        
        # Calculate 52-week change
        oldest = prices[-1] if len(prices) == WEEK_52_WINDOW else prices[-1]
        change_52w_pct = ((current.close - oldest.close) / oldest.close) * 100
        
        return {
            "current_price": current.close,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "avg_close": round(avg_close, 2),
            "volatility": current.volatility_20d,
            "rsi": current.rsi_14,
            "change_52w_pct": round(change_52w_pct, 2),
        }
    
    # === Comparison & Correlation ===
    
    def get_comparison_data(
        self, 
        symbol1: str, 
        symbol2: str
    ) -> Tuple[Optional[dict], Optional[dict], Optional[float]]:
        """
        Get comparison data for two stocks.
        
        Returns:
            Tuple of (summary1, summary2, correlation)
        """
        summary1 = self.get_52_week_summary(symbol1)
        summary2 = self.get_52_week_summary(symbol2)
        
        if not summary1 or not summary2:
            return summary1, summary2, None
        
        # Calculate correlation from close prices
        prices1 = self.get_price_history(symbol1)
        prices2 = self.get_price_history(symbol2)
        
        if not prices1 or not prices2:
            return summary1, summary2, None
        
        # Convert to series with date index
        series1 = pd.Series(
            [p.close for p in prices1],
            index=[p.date for p in prices1]
        )
        series2 = pd.Series(
            [p.close for p in prices2],
            index=[p.date for p in prices2]
        )
        
        correlation = AnalyticsService.compute_correlation(series1, series2)
        
        return summary1, summary2, correlation
    
    # === Top Movers ===
    
    def get_top_movers(self, limit: int = 5) -> Tuple[List[dict], List[dict]]:
        """
        Get top gainers and losers based on most recent daily return.
        
        Args:
            limit: Number of stocks to return for each category
            
        Returns:
            Tuple of (gainers, losers) as lists of dicts
        """
        # Get the most recent trading date
        latest_date = (
            self.db.query(func.max(DailyPrice.date))
            .scalar()
        )
        
        if not latest_date:
            return [], []
        
        # Get all prices for latest date
        latest_prices = (
            self.db.query(DailyPrice)
            .filter(DailyPrice.date == latest_date)
            .all()
        )
        
        # Sort by daily return
        sorted_prices = sorted(
            latest_prices,
            key=lambda p: p.daily_return or 0,
            reverse=True
        )
        
        # Get company names
        companies = {c.symbol: c.name for c in self.get_all_companies()}
        
        def to_mover_dict(price: DailyPrice) -> dict:
            return {
                "symbol": price.symbol,
                "name": companies.get(price.symbol, price.symbol),
                "close": price.close,
                "change_pct": round((price.daily_return or 0) * 100, 2),
            }
        
        gainers = [to_mover_dict(p) for p in sorted_prices[:limit]]
        losers = [to_mover_dict(p) for p in sorted_prices[-limit:][::-1]]
        
        return gainers, losers
    
    def get_latest_trading_date(self) -> Optional[date]:
        """Get the most recent trading date in the database."""
        return self.db.query(func.max(DailyPrice.date)).scalar()
