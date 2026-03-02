import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    merchant: str = Field(..., min_length=1, max_length=100)
    purchase_datetime: datetime
    amount: Decimal = Field(..., ge=Decimal("0.01"), le=Decimal("999999.99"))
    category_id: uuid.UUID
    spender_id: uuid.UUID
    payment_method_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)


class ExpenseUpdate(BaseModel):
    """PATCH — partial update. All fields optional."""

    merchant: str | None = Field(None, min_length=1, max_length=100)
    purchase_datetime: datetime | None = None
    amount: Decimal | None = Field(None, ge=Decimal("0.01"), le=Decimal("999999.99"))
    category_id: uuid.UUID | None = None
    spender_id: uuid.UUID | None = None
    payment_method_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=500)
    tags: list[str] | None = None


class TagInfo(BaseModel):
    id: uuid.UUID
    name: str
    model_config = {"from_attributes": True}


class ExpenseLineResponse(BaseModel):
    id: uuid.UUID
    amount: Decimal
    category_id: uuid.UUID
    category_name: str | None = None
    line_order: int
    tags: list[TagInfo] = []


class SpenderInfo(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    space_id: uuid.UUID
    merchant: str
    purchase_datetime: datetime
    total_amount: Decimal
    spender: SpenderInfo
    payment_method_id: uuid.UUID | None
    notes: str | None
    status: str
    lines: list[ExpenseLineResponse] = []
    created_at: datetime
    updated_at: datetime


class ExpenseListResponse(BaseModel):
    data: list[ExpenseResponse]
    next_cursor: str | None = None
