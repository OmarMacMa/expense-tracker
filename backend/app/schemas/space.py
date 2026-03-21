import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SpaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    currency_code: str = Field(..., min_length=3, max_length=3)
    timezone: str = Field(..., min_length=1, max_length=100)
    default_tax_pct: Decimal | None = Field(None, ge=0, le=Decimal("99.99"))
    seed_default_categories: bool = False


class SpaceUpdate(BaseModel):
    """PUT — full replacement of editable fields. Currency is immutable."""

    name: str = Field(..., min_length=1, max_length=100)
    timezone: str = Field(..., min_length=1, max_length=100)
    default_tax_pct: Decimal | None = Field(None, ge=0, le=Decimal("99.99"))


class SpaceResponse(BaseModel):
    id: uuid.UUID
    name: str
    currency_code: str
    timezone: str
    default_tax_pct: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    email: str
    avatar_url: str | None
    joined_at: datetime
