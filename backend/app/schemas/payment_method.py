import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PaymentMethodCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=50)


class PaymentMethodUpdate(BaseModel):
    """PATCH — partial update. Only label for now."""

    label: str | None = Field(None, min_length=1, max_length=50)


class PaymentMethodResponse(BaseModel):
    id: uuid.UUID
    label: str
    is_system: bool
    owner_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
