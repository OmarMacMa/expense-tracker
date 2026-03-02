import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class CategoryUpdate(BaseModel):
    """PUT — full replacement of category name."""

    name: str = Field(..., min_length=1, max_length=100)


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    normalized_name: str
    is_system: bool
    created_at: datetime

    model_config = {"from_attributes": True}
