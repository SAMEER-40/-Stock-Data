"""
Prediction Service
==================
Provides basic ML-based price forecasting using Linear Regression.
This is a simplified model for demonstration purposes.
"""
import numpy as np
from typing import List, Dict, Any
from datetime import datetime, timedelta


class PredictionService:
    """
    Simple Linear Regression-based price predictor.
    Uses the last N days to forecast the next M days.
    """
    
    LOOKBACK_DAYS = 60  # Use last 60 days for training
    FORECAST_DAYS = 7   # Predict next 7 days
    
    @staticmethod
    def predict_prices(prices: List[float], dates: List[str]) -> Dict[str, Any]:
        """
        Generate price predictions using Linear Regression.
        
        Args:
            prices: List of closing prices (chronological order)
            dates: List of date strings corresponding to prices
            
        Returns:
            Dict with prediction data and model metrics
        """
        if len(prices) < 30:
            return {
                "error": "Insufficient data for prediction",
                "predictions": [],
                "confidence": 0
            }
        
        # Use last LOOKBACK_DAYS for training
        lookback = min(PredictionService.LOOKBACK_DAYS, len(prices))
        train_prices = prices[-lookback:]
        
        # Feature: day index (0, 1, 2, ...)
        X = np.arange(lookback).reshape(-1, 1)
        y = np.array(train_prices)
        
        # Simple Linear Regression (closed-form solution)
        X_mean = np.mean(X)
        y_mean = np.mean(y)
        
        numerator = np.sum((X.flatten() - X_mean) * (y - y_mean))
        denominator = np.sum((X.flatten() - X_mean) ** 2)
        
        if denominator == 0:
            return {"error": "Cannot compute regression", "predictions": [], "confidence": 0}
        
        slope = numerator / denominator
        intercept = y_mean - slope * X_mean
        
        # R-squared for confidence metric
        y_pred_train = slope * X.flatten() + intercept
        ss_res = np.sum((y - y_pred_train) ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Generate future predictions
        last_date = datetime.strptime(dates[-1], "%Y-%m-%d")
        future_X = np.arange(lookback, lookback + PredictionService.FORECAST_DAYS)
        future_prices = slope * future_X + intercept
        
        predictions = []
        for i, price in enumerate(future_prices):
            future_date = last_date + timedelta(days=i + 1)
            # Skip weekends (simple approximation)
            while future_date.weekday() >= 5:
                future_date += timedelta(days=1)
            
            predictions.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "predicted_price": round(float(price), 2),
                "is_forecast": True
            })
        
        # Trend direction
        trend = "bullish" if slope > 0 else "bearish" if slope < 0 else "neutral"
        
        return {
            "model": "linear_regression",
            "lookback_days": lookback,
            "forecast_days": PredictionService.FORECAST_DAYS,
            "trend": trend,
            "slope_per_day": round(float(slope), 4),
            "r_squared": round(float(r_squared), 4),
            "confidence": round(float(max(0, min(r_squared * 100, 100))), 1),
            "predictions": predictions
        }


class SentimentService:
    """
    Mock Sentiment Index based on technical indicators.
    Combines RSI, volatility, and price momentum into a composite score.
    """
    
    @staticmethod
    def calculate_sentiment(
        rsi: float | None,
        volatility: float | None,
        price_change_pct: float | None,
        ma7: float | None,
        ma20: float | None,
        current_price: float | None
    ) -> Dict[str, Any]:
        """
        Calculate a mock sentiment index (0-100).
        
        Components:
        - RSI contribution (40%): Normalized RSI
        - Volatility contribution (20%): Lower volatility = more positive
        - Momentum contribution (20%): Price vs MA crossover
        - Trend contribution (20%): Recent price change
        
        Returns:
            Dict with sentiment score and breakdown
        """
        components = {}
        weights = {"rsi": 0.4, "volatility": 0.2, "momentum": 0.2, "trend": 0.2}
        
        # RSI Component (40%)
        if rsi is not None:
            # RSI 50 = neutral, above 50 = bullish, below 50 = bearish
            rsi_score = rsi  # Already 0-100
            components["rsi"] = {"score": round(rsi_score, 1), "weight": weights["rsi"]}
        else:
            rsi_score = 50
            components["rsi"] = {"score": 50, "weight": weights["rsi"], "note": "default"}
        
        # Volatility Component (20%) - Lower volatility = higher score
        if volatility is not None:
            # Assume volatility typically ranges 0.1 to 0.5 (10% to 50% annualized)
            vol_normalized = min(volatility / 0.5, 1.0)  # Cap at 50%
            vol_score = (1 - vol_normalized) * 100  # Invert: low vol = high score
            components["volatility"] = {"score": round(vol_score, 1), "weight": weights["volatility"]}
        else:
            vol_score = 50
            components["volatility"] = {"score": 50, "weight": weights["volatility"], "note": "default"}
        
        # Momentum Component (20%) - Price vs Moving Averages
        if ma7 is not None and ma20 is not None and current_price is not None:
            # Golden cross scenario
            above_ma7 = current_price > ma7
            above_ma20 = current_price > ma20
            ma7_above_ma20 = ma7 > ma20
            
            momentum_score = 50  # Base
            if above_ma7 and above_ma20:
                momentum_score = 75
            if ma7_above_ma20:
                momentum_score += 15
            if not above_ma7 and not above_ma20:
                momentum_score = 25
            
            momentum_score = min(max(momentum_score, 0), 100)
            components["momentum"] = {"score": round(momentum_score, 1), "weight": weights["momentum"]}
        else:
            momentum_score = 50
            components["momentum"] = {"score": 50, "weight": weights["momentum"], "note": "default"}
        
        # Trend Component (20%) - Recent price change
        if price_change_pct is not None:
            # Map -50% to +50% change to 0-100 score
            trend_score = 50 + price_change_pct  # Simple linear mapping
            trend_score = min(max(trend_score, 0), 100)
            components["trend"] = {"score": round(trend_score, 1), "weight": weights["trend"]}
        else:
            trend_score = 50
            components["trend"] = {"score": 50, "weight": weights["trend"], "note": "default"}
        
        # Weighted Average
        final_score = (
            rsi_score * weights["rsi"] +
            vol_score * weights["volatility"] +
            momentum_score * weights["momentum"] +
            trend_score * weights["trend"]
        )
        
        # Interpret
        if final_score >= 70:
            interpretation = "strong_bullish"
            label = "Strong Buy Signal"
        elif final_score >= 55:
            interpretation = "bullish"
            label = "Bullish"
        elif final_score >= 45:
            interpretation = "neutral"
            label = "Neutral"
        elif final_score >= 30:
            interpretation = "bearish"
            label = "Bearish"
        else:
            interpretation = "strong_bearish"
            label = "Strong Sell Signal"
        
        return {
            "sentiment_score": round(final_score, 1),
            "interpretation": interpretation,
            "label": label,
            "components": components,
            "disclaimer": "This is a mock sentiment index for demonstration purposes only. Not financial advice."
        }
