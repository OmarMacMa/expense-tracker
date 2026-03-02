import uuid

from pydantic import BaseModel


class MerchantSuggestion(BaseModel):
    name: str
    use_count: int

    model_config = {"from_attributes": True}


class MerchantCategoryResponse(BaseModel):
    name: str
    last_category_id: uuid.UUID | None
    last_category_name: str | None
