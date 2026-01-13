"""
Pydantic models for API response serialization.

All responses are clearly typed for Swagger documentation.
Nullable fields use Optional to handle missing analytics during initial rolling windows.
"""
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


class CompanyResponse(BaseModel):
    """Response model for company listing."""
    symbol: str = Field(..., example="RELIANCE.NS")
    name: str = Field(..., example="Reliance Industries")
    sector: Optional[str] = Field(None, example="Energy")
    
    class Config:
        from_attributes = True


class DailyPriceResponse(BaseModel):
    """Response model for daily stock data."""
    date: date
    open: float = Field(..., example=2450.50)
    high: float = Field(..., example=2480.00)
    low: float = Field(..., example=2440.00)
    close: float = Field(..., example=2465.75)
    volume: Optional[int] = Field(None, example=12500000)
    daily_return: Optional[float] = Field(None, example=0.0062, description="(close-open)/open")
    ma_7: Optional[float] = Field(None, example=2455.30, description="7-day moving average")
    ma_20: Optional[float] = Field(None, example=2420.15, description="20-day moving average")
    volatility_20d: Optional[float] = Field(None, example=0.245, description="Annualized volatility")
    rsi_14: Optional[float] = Field(None, example=58.5, description="14-day RSI (0-100)")
    
    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    """52-week summary statistics for a stock."""
    symbol: str
    name: str
    current_price: float = Field(..., example=2465.75)
    high_52w: float = Field(..., example=2850.00, description="52-week high")
    low_52w: float = Field(..., example=2100.00, description="52-week low")
    avg_close: float = Field(..., example=2425.50, description="Average close over period")
    volatility: Optional[float] = Field(None, example=0.28, description="Current volatility score")
    rsi: Optional[float] = Field(None, example=55.3, description="Current RSI-14")
    change_52w_pct: float = Field(..., example=12.5, description="52-week price change %")


class StockSummary(BaseModel):
    """Summary data for one stock in comparison."""
    symbol: str
    name: str
    current_price: float
    high_52w: float
    low_52w: float
    avg_close: float
    volatility: Optional[float]


class CompareResponse(BaseModel):
    """Comparison between two stocks."""
    stock1: StockSummary
    stock2: StockSummary
    correlation: Optional[float] = Field(
        None, 
        example=0.72,
        description="Price correlation coefficient (-1 to 1)"
    )
    volatility_ratio: Optional[float] = Field(
        None,
        example=1.25,
        description="Volatility of stock1 / volatility of stock2"
    )


class MoverStock(BaseModel):
    """Stock in gainers/losers list."""
    symbol: str
    name: str
    close: float
    change_pct: float = Field(..., example=2.5, description="Daily change %")


class TopMoversResponse(BaseModel):
    """Top gainers and losers for the day."""
    date: date
    gainers: List[MoverStock]
    losers: List[MoverStock]


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str = Field(..., example="Symbol 'INVALID' not found in database")


class PredictionPoint(BaseModel):
    """Single prediction data point."""
    date: str
    predicted_price: float
    is_forecast: bool = True


class PredictionResponse(BaseModel):
    """ML-based price prediction response."""
    symbol: str
    model: str = Field(..., example="linear_regression")
    lookback_days: int = Field(..., example=60)
    forecast_days: int = Field(..., example=7)
    trend: str = Field(..., example="bullish", description="bullish/bearish/neutral")
    slope_per_day: float = Field(..., example=2.35, description="Price change per day")
    r_squared: float = Field(..., example=0.85, description="Model fit quality (0-1)")
    confidence: float = Field(..., example=85.0, description="Confidence % (0-100)")
    predictions: List[PredictionPoint]


class SentimentComponent(BaseModel):
    """Individual sentiment component."""
    score: float
    weight: float
    note: Optional[str] = None


class SentimentResponse(BaseModel):
    """Mock sentiment index response."""
    symbol: str
    sentiment_score: float = Field(..., example=68.5, description="Composite score 0-100")
    interpretation: str = Field(..., example="bullish")
    label: str = Field(..., example="Bullish")
    components: dict  # RSI, volatility, momentum, trend breakdowns
    disclaimer: str

