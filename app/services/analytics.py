"""
Analytics computation service.

All financial metric computations are centralized here.
No analytics logic should exist in API routes.

Design Principles:
1. Vectorized Pandas operations (O(n) complexity)
2. No look-ahead bias - rolling windows use only historical data
3. Deterministic: same input → same output
"""
import numpy as np
import pandas as pd
from typing import Optional
import math

from app.config import (
    MA_WINDOW_7,
    MA_WINDOW_20,
    VOLATILITY_WINDOW,
    RSI_WINDOW,
    WEEK_52_WINDOW,
)


class AnalyticsService:
    """
    Financial analytics computation engine.
    
    All methods operate on Pandas DataFrames for efficient vectorized computation.
    """
    
    @staticmethod
    def compute_daily_return(df: pd.DataFrame) -> pd.Series:
        """
        Calculate intraday return.
        
        Formula: (close - open) / open
        
        Returns:
            Series of daily returns (as decimals, not percentages)
        """
        return (df["close"] - df["open"]) / df["open"]
    
    @staticmethod
    def compute_moving_average(series: pd.Series, window: int) -> pd.Series:
        """
        Calculate simple moving average.
        
        Args:
            series: Price series (typically close prices)
            window: Number of periods for rolling average
            
        Returns:
            Series with SMA values (NaN for initial periods)
        """
        return series.rolling(window=window, min_periods=window).mean()
    
    @staticmethod
    def compute_volatility(daily_returns: pd.Series, window: int = VOLATILITY_WINDOW) -> pd.Series:
        """
        Calculate annualized volatility (primary creative metric).
        
        Formula: std(daily_returns, window) * sqrt(252)
        
        The sqrt(252) factor annualizes the daily volatility assuming
        252 trading days per year.
        
        Args:
            daily_returns: Series of daily return values
            window: Rolling window size (default: 20 days)
            
        Returns:
            Series of annualized volatility scores
        """
        rolling_std = daily_returns.rolling(window=window, min_periods=window).std()
        annualized = rolling_std * math.sqrt(252)
        return annualized
    
    @staticmethod
    def compute_rsi(series: pd.Series, window: int = RSI_WINDOW) -> pd.Series:
        """
        Calculate Relative Strength Index (momentum indicator).
        
        RSI measures the magnitude of recent price changes to evaluate
        overbought or oversold conditions.
        
        Formula:
            RSI = 100 - (100 / (1 + RS))
            RS = Average Gain / Average Loss over window
        
        Interpretation:
            RSI > 70: Overbought (potential sell signal)
            RSI < 30: Oversold (potential buy signal)
        
        Args:
            series: Close price series
            window: RSI period (default: 14 days)
            
        Returns:
            Series of RSI values (0-100 scale)
        """
        # Calculate price changes
        delta = series.diff()
        
        # Separate gains and losses
        gains = delta.clip(lower=0)
        losses = (-delta).clip(lower=0)
        
        # Calculate average gains and losses using exponential moving average
        # This is the Wilder smoothing method (standard for RSI)
        avg_gain = gains.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
        avg_loss = losses.ewm(alpha=1/window, min_periods=window, adjust=False).mean()
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Handle edge case: if avg_loss is 0, RS is infinite → RSI = 100
        rsi = rsi.replace([np.inf, -np.inf], np.nan)
        
        return rsi
    
    @staticmethod
    def compute_52_week_stats(df: pd.DataFrame) -> dict:
        """
        Calculate 52-week high, low, and average close.
        
        Args:
            df: DataFrame with at least 'close' column, sorted by date
            
        Returns:
            Dictionary with high_52w, low_52w, avg_close
        """
        # Use last 252 trading days (approximately 1 year)
        window_df = df.tail(WEEK_52_WINDOW)
        
        return {
            "high_52w": float(window_df["close"].max()),
            "low_52w": float(window_df["close"].min()),
            "avg_close": float(window_df["close"].mean()),
        }
    
    @staticmethod
    def compute_correlation(series1: pd.Series, series2: pd.Series) -> Optional[float]:
        """
        Calculate Pearson correlation between two price series.
        
        Args:
            series1: First price series
            series2: Second price series
            
        Returns:
            Correlation coefficient (-1 to 1), or None if insufficient data
        """
        # Align series by index (date)
        aligned = pd.concat([series1, series2], axis=1, join="inner")
        
        if len(aligned) < 30:  # Need sufficient data for meaningful correlation
            return None
        
        corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
        
        return float(corr) if not pd.isna(corr) else None
    
    @classmethod
    def compute_all_metrics(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all metrics for a stock's price history.
        
        This is the main entry point called during data ingestion.
        All metrics are computed in a single vectorized pass.
        
        Args:
            df: DataFrame with columns: date, open, high, low, close, volume
                Must be sorted by date ascending
        
        Returns:
            DataFrame with additional columns: daily_return, ma_7, ma_20, 
            volatility_20d, rsi_14
        """
        df = df.copy()
        
        # Ensure sorted by date (critical for time-series)
        df = df.sort_values("date").reset_index(drop=True)
        
        # Compute all metrics
        df["daily_return"] = cls.compute_daily_return(df)
        df["ma_7"] = cls.compute_moving_average(df["close"], MA_WINDOW_7)
        df["ma_20"] = cls.compute_moving_average(df["close"], MA_WINDOW_20)
        df["volatility_20d"] = cls.compute_volatility(df["daily_return"], VOLATILITY_WINDOW)
        df["rsi_14"] = cls.compute_rsi(df["close"], RSI_WINDOW)
        
        return df
