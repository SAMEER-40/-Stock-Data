"""
FastAPI route definitions.

All endpoints are defined here with proper typing and documentation.
No business logic - delegates to service layer.

Error Handling:
- 404: Symbol not found
- 422: Invalid request parameters
- 503: Data source unavailable
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.data_service import DataService
from app.schemas.stock import (
    CompanyResponse,
    DailyPriceResponse,
    SummaryResponse,
    CompareResponse,
    StockSummary,
    TopMoversResponse,
    MoverStock,
)

router = APIRouter()


# === Company Endpoints ===

@router.get(
    "/companies",
    response_model=List[CompanyResponse],
    summary="List all companies",
    description="Returns all tracked companies with symbol, name, and sector.",
)
def get_companies(db: Session = Depends(get_db)) -> List[CompanyResponse]:
    """List all available companies in the database."""
    service = DataService(db)
    companies = service.get_all_companies()
    return [CompanyResponse.model_validate(c) for c in companies]


# === Price Data Endpoints ===

@router.get(
    "/data/{symbol}",
    response_model=List[DailyPriceResponse],
    summary="Get stock price data",
    description="Returns the last N days of OHLCV data with computed analytics.",
    responses={
        404: {"description": "Symbol not found"},
    },
)
def get_stock_data(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of days"),
    db: Session = Depends(get_db),
) -> List[DailyPriceResponse]:
    """
    Get last N days of stock data for a symbol.
    
    Includes computed analytics: daily_return, ma_7, ma_20, volatility_20d, rsi_14
    """
    service = DataService(db)
    
    # Validate symbol exists
    if not service.symbol_exists(symbol):
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found in database"
        )
    
    prices = service.get_recent_prices(symbol, days)
    
    # Sort ascending for client (API returns most recent first by default)
    prices = sorted(prices, key=lambda p: p.date)
    
    return [DailyPriceResponse.model_validate(p) for p in prices]


# === Summary Endpoints ===

@router.get(
    "/summary/{symbol}",
    response_model=SummaryResponse,
    summary="Get 52-week summary",
    description="Returns 52-week high, low, average close, and current analytics.",
    responses={
        404: {"description": "Symbol not found"},
    },
)
def get_summary(
    symbol: str,
    db: Session = Depends(get_db),
) -> SummaryResponse:
    """Get 52-week summary statistics for a stock."""
    service = DataService(db)
    
    # Get company info
    company = service.get_company_by_symbol(symbol)
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found in database"
        )
    
    # Get summary stats
    summary = service.get_52_week_summary(symbol)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No price data found for symbol '{symbol}'"
        )
    
    return SummaryResponse(
        symbol=symbol,
        name=company.name,
        **summary
    )


# === Comparison Endpoint ===

@router.get(
    "/compare",
    response_model=CompareResponse,
    summary="Compare two stocks",
    description="Compares two stocks with correlation analysis.",
    responses={
        404: {"description": "One or both symbols not found"},
        422: {"description": "Invalid parameters"},
    },
)
def compare_stocks(
    symbol1: str = Query(..., description="First stock symbol"),
    symbol2: str = Query(..., description="Second stock symbol"),
    db: Session = Depends(get_db),
) -> CompareResponse:
    """
    Compare two stocks.
    
    Returns summary statistics for each stock plus correlation coefficient.
    """
    if symbol1 == symbol2:
        raise HTTPException(
            status_code=422,
            detail="symbol1 and symbol2 must be different"
        )
    
    service = DataService(db)
    
    # Validate both symbols exist
    company1 = service.get_company_by_symbol(symbol1)
    company2 = service.get_company_by_symbol(symbol2)
    
    if not company1:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol1}' not found in database"
        )
    if not company2:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol2}' not found in database"
        )
    
    # Get comparison data
    summary1, summary2, correlation = service.get_comparison_data(symbol1, symbol2)
    
    if not summary1 or not summary2:
        raise HTTPException(
            status_code=404,
            detail="Insufficient price data for comparison"
        )
    
    # Calculate volatility ratio
    vol_ratio = None
    if summary1.get("volatility") and summary2.get("volatility"):
        vol_ratio = round(summary1["volatility"] / summary2["volatility"], 3)
    
    return CompareResponse(
        stock1=StockSummary(
            symbol=symbol1,
            name=company1.name,
            current_price=summary1["current_price"],
            high_52w=summary1["high_52w"],
            low_52w=summary1["low_52w"],
            avg_close=summary1["avg_close"],
            volatility=summary1.get("volatility"),
        ),
        stock2=StockSummary(
            symbol=symbol2,
            name=company2.name,
            current_price=summary2["current_price"],
            high_52w=summary2["high_52w"],
            low_52w=summary2["low_52w"],
            avg_close=summary2["avg_close"],
            volatility=summary2.get("volatility"),
        ),
        correlation=round(correlation, 3) if correlation else None,
        volatility_ratio=vol_ratio,
    )


# === Top Movers Endpoint ===

@router.get(
    "/top-movers",
    response_model=TopMoversResponse,
    summary="Get top gainers and losers",
    description="Returns top 5 gainers and losers based on daily return.",
)
def get_top_movers(
    limit: int = Query(default=5, ge=1, le=20, description="Number of stocks per category"),
    db: Session = Depends(get_db),
) -> TopMoversResponse:
    """Get today's top gainers and losers."""
    service = DataService(db)
    
    latest_date = service.get_latest_trading_date()
    if not latest_date:
        raise HTTPException(
            status_code=503,
            detail="No trading data available"
        )
    
    gainers, losers = service.get_top_movers(limit)
    
    return TopMoversResponse(
        date=latest_date,
        gainers=[MoverStock(**g) for g in gainers],
        losers=[MoverStock(**l) for l in losers],
    )


# === Analytics Endpoint ===

@router.get(
    "/analytics/{symbol}",
    summary="Get detailed analytics",
    description="Returns current analytics values: RSI, volatility, trend assessment.",
    responses={
        404: {"description": "Symbol not found"},
    },
)
def get_analytics(
    symbol: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get detailed analytics for a stock."""
    service = DataService(db)
    
    if not service.symbol_exists(symbol):
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found in database"
        )
    
    latest = service.get_latest_price(symbol)
    if not latest:
        raise HTTPException(
            status_code=404,
            detail=f"No price data for symbol '{symbol}'"
        )
    
    # Determine trend from RSI
    trend = "neutral"
    if latest.rsi_14:
        if latest.rsi_14 > 70:
            trend = "overbought"
        elif latest.rsi_14 < 30:
            trend = "oversold"
        elif latest.rsi_14 > 50:
            trend = "bullish"
        else:
            trend = "bearish"
    
    # Determine volatility level
    vol_level = "normal"
    if latest.volatility_20d:
        if latest.volatility_20d > 0.4:
            vol_level = "high"
        elif latest.volatility_20d < 0.2:
            vol_level = "low"
    
    return {
        "symbol": symbol,
        "date": latest.date,
        "close": latest.close,
        "daily_return": round(latest.daily_return * 100, 2) if latest.daily_return else None,
        "daily_return_label": "% change from open",
        "ma_7": round(latest.ma_7, 2) if latest.ma_7 else None,
        "ma_20": round(latest.ma_20, 2) if latest.ma_20 else None,
        "rsi_14": round(latest.rsi_14, 2) if latest.rsi_14 else None,
        "rsi_interpretation": trend,
        "volatility_20d": round(latest.volatility_20d, 4) if latest.volatility_20d else None,
        "volatility_level": vol_level,
        "volatility_label": "Annualized 20-day volatility",
    }


# === Prediction Endpoint ===

@router.get(
    "/prediction/{symbol}",
    summary="Get price prediction",
    description="Returns ML-based price prediction using Linear Regression. For demonstration purposes.",
    responses={
        404: {"description": "Symbol not found"},
    },
)
def get_prediction(
    symbol: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Generate 7-day price forecast using Linear Regression.
    
    Uses the last 60 days of data to train a simple model.
    Returns predicted prices, trend direction, and confidence score.
    """
    from app.services.prediction import PredictionService
    
    service = DataService(db)
    
    if not service.symbol_exists(symbol):
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found in database"
        )
    
    # Get historical prices for prediction
    prices = service.get_recent_prices(symbol, days=90)
    
    if len(prices) < 30:
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient data for prediction (need at least 30 days)"
        )
    
    # Sort by date ascending
    prices = sorted(prices, key=lambda p: p.date)
    
    # Extract close prices and dates
    close_prices = [p.close for p in prices]
    dates = [p.date.strftime("%Y-%m-%d") for p in prices]
    
    # Generate predictions
    prediction_result = PredictionService.predict_prices(close_prices, dates)
    
    if "error" in prediction_result:
        raise HTTPException(
            status_code=500,
            detail=prediction_result["error"]
        )
    
    return {
        "symbol": symbol,
        **prediction_result
    }


# === Sentiment Endpoint ===

@router.get(
    "/sentiment/{symbol}",
    summary="Get sentiment index",
    description="Returns a mock sentiment score based on technical indicators. For demonstration purposes.",
    responses={
        404: {"description": "Symbol not found"},
    },
)
def get_sentiment(
    symbol: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Calculate mock sentiment index (0-100).
    
    Composite of:
    - RSI (40%)
    - Volatility (20%)
    - Price vs Moving Averages (20%)
    - Recent trend (20%)
    """
    from app.services.prediction import SentimentService
    
    service = DataService(db)
    
    if not service.symbol_exists(symbol):
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found in database"
        )
    
    # Get latest price data
    latest = service.get_latest_price(symbol)
    if not latest:
        raise HTTPException(
            status_code=404,
            detail=f"No price data for symbol '{symbol}'"
        )
    
    # Get 52-week summary for price change %
    summary = service.get_52_week_summary(symbol)
    price_change_pct = summary.get("change_52w_pct") if summary else None
    
    # Calculate sentiment
    sentiment_result = SentimentService.calculate_sentiment(
        rsi=latest.rsi_14,
        volatility=latest.volatility_20d,
        price_change_pct=price_change_pct,
        ma7=latest.ma_7,
        ma20=latest.ma_20,
        current_price=latest.close
    )
    
    return {
        "symbol": symbol,
        **sentiment_result
    }


# === Health Check ===


@router.get(
    "/health",
    summary="Health check",
    description="Returns API health status and database connectivity.",
)
def health_check(db: Session = Depends(get_db)) -> dict:
    """API health check endpoint."""
    service = DataService(db)
    
    try:
        companies = len(service.get_all_companies())
        latest_date = service.get_latest_trading_date()
        
        return {
            "status": "healthy",
            "database": "connected",
            "companies_tracked": companies,
            "latest_data_date": str(latest_date) if latest_date else None,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "error",
            "error": str(e),
        }
