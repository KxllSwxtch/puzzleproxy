from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class CurrencyRateData(BaseModel):
    """Currency rate data structure"""
    rubToKrwRate: float = Field(..., description="RUB to KRW exchange rate (adjusted)")
    originalRate: Optional[float] = Field(None, description="Original rate from Naver before adjustment")


class UsdCurrencyRateData(BaseModel):
    """USD currency rate data structure"""
    usdToKrwRate: float = Field(..., description="USD to KRW exchange rate (adjusted)")
    originalRate: Optional[float] = Field(None, description="Original rate from Naver before adjustment")


class UsdCurrencyRateResponse(BaseModel):
    """Standardized USD currency rate response"""
    success: bool = Field(..., description="Whether the request was successful")
    data: UsdCurrencyRateData = Field(..., description="USD currency rate data")
    source: str = Field(..., description="Source of the rate (naver or fallback)")
    lastUpdated: str = Field(..., description="ISO timestamp of when the rate was fetched")
    error: Optional[str] = Field(None, description="Error message if request failed")


class CurrencyRateResponse(BaseModel):
    """Standardized currency rate response"""
    success: bool = Field(..., description="Whether the request was successful")
    data: CurrencyRateData = Field(..., description="Currency rate data")
    source: str = Field(..., description="Source of the rate (naver or fallback)")
    lastUpdated: str = Field(..., description="ISO timestamp of when the rate was fetched")
    error: Optional[str] = Field(None, description="Error message if request failed")


class NaverApiResponse(BaseModel):
    """Naver API response structure for internal use"""
    pkid: int
    count: int
    country: list
    calculatorMessage: str