import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SummaryResponse(BaseModel):
    total_spent: Decimal
    delta_pct: Decimal | None  # null if no prior data
    period_label: str
    window_start: datetime
    window_end: datetime


class TrendPoint(BaseModel):
    day: int  # 0-based day of period
    cumulative: Decimal


class SpendingTrendResponse(BaseModel):
    current_series: list[TrendPoint]
    average_series: list[TrendPoint]
    timeframe: str


class CategoryBreakdownItem(BaseModel):
    category_id: uuid.UUID
    category_name: str
    total: Decimal
    percentage: Decimal


class MerchantLeaderboardItem(BaseModel):
    merchant: str
    total: Decimal
    count: int


class SpenderBreakdownItem(BaseModel):
    spender_id: uuid.UUID
    display_name: str
    total: Decimal
    percentage: Decimal
