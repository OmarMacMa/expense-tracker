import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LimitFilterCreate(BaseModel):
    filter_type: str  # "category" in MVP
    filter_value: str  # category UUID as string


class LimitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    timeframe: str = Field(...)  # "weekly" or "monthly" in MVP
    threshold_amount: Decimal = Field(..., ge=Decimal("0.01"), le=Decimal("999999.99"))
    warning_pct: Decimal = Field(
        default=Decimal("0.6000"), ge=Decimal("0"), le=Decimal("1")
    )
    filters: list[LimitFilterCreate] = Field(default_factory=list)


class LimitUpdate(BaseModel):
    """PATCH — partial update."""

    name: str | None = Field(None, min_length=1, max_length=100)
    threshold_amount: Decimal | None = Field(
        None, ge=Decimal("0.01"), le=Decimal("999999.99")
    )
    warning_pct: Decimal | None = Field(None, ge=Decimal("0"), le=Decimal("1"))
    filters: list[LimitFilterCreate] | None = None


class LimitFilterResponse(BaseModel):
    id: uuid.UUID
    filter_type: str
    filter_value: str

    model_config = {"from_attributes": True}


class LimitResponse(BaseModel):
    id: uuid.UUID
    name: str
    timeframe: str
    threshold_amount: Decimal
    warning_pct: Decimal
    filters: list[LimitFilterResponse] = []
    created_at: datetime
    # Progress fields (computed on read)
    spent: Decimal = Decimal("0")
    progress: Decimal = Decimal("0")
    days_remaining: int = 0
    status: str = "ok"  # ok | warning | critical | exceeded
