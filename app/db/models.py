"""
SQLAlchemy ORM models for stock data.

Database Schema:
- companies: Master list of tracked stocks
- daily_prices: OHLCV data with pre-computed analytics

Design Decisions:
1. Derived metrics (daily_return, ma_7, volatility, rsi) stored at ingestion time
   to avoid recomputation on every API call.
2. Composite index on (symbol, date) for efficient time-series queries.
3. No cascade deletes - data integrity is critical in financial systems.
"""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, BigInteger, Date, DateTime,
    Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Company(Base):
    """
    Master table of tracked companies.
    
    Each company is identified by its stock exchange symbol (e.g., RELIANCE.NS).
    """
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    sector = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Company(symbol='{self.symbol}', name='{self.name}')>"


class DailyPrice(Base):
    """
    Daily OHLCV data with pre-computed analytics.
    
    Each row represents one trading day for one stock symbol.
    Analytics are computed at ingestion time using Pandas vectorized operations.
    
    Metrics:
    - daily_return: (close - open) / open
    - ma_7: 7-day simple moving average of close price
    - ma_20: 20-day simple moving average of close price
    - volatility_20d: Annualized volatility (20-day rolling std dev * sqrt(252))
    - rsi_14: 14-day Relative Strength Index (0-100)
    """
    __tablename__ = "daily_prices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # OHLCV fields
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=True)
    
    # Pre-computed analytics (nullable for initial rolling window days)
    daily_return = Column(Float, nullable=True)
    ma_7 = Column(Float, nullable=True)
    ma_20 = Column(Float, nullable=True)
    volatility_20d = Column(Float, nullable=True)
    rsi_14 = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Composite index for time-series queries: WHERE symbol = ? ORDER BY date
    __table_args__ = (
        Index("ix_daily_prices_symbol_date", "symbol", "date"),
        UniqueConstraint("symbol", "date", name="uq_symbol_date"),
    )
    
    def __repr__(self) -> str:
        return f"<DailyPrice(symbol='{self.symbol}', date='{self.date}', close={self.close})>"
