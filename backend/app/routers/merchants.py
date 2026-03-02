import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.space import get_current_space_member
from app.models import SpaceMember
from app.schemas.merchant import MerchantCategoryResponse, MerchantSuggestion
from app.services.merchant import get_category_suggestion, suggest_merchants

router = APIRouter(prefix="/api/v1/spaces/{space_id}", tags=["merchants"])


@router.get("/merchants/suggest", response_model=list[MerchantSuggestion])
async def suggest_merchants_endpoint(
    space_id: uuid.UUID,
    q: str = Query("", min_length=0, max_length=100),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[MerchantSuggestion]:
    """Autocomplete merchant names by prefix."""
    merchants = await suggest_merchants(db, space_id, q)
    return [MerchantSuggestion.model_validate(m) for m in merchants]


@router.get("/merchants/{name}/category", response_model=MerchantCategoryResponse)
async def get_merchant_category_endpoint(
    space_id: uuid.UUID,
    name: str,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> MerchantCategoryResponse:
    """Get the last category used for a merchant."""
    result = await get_category_suggestion(db, space_id, name)
    return MerchantCategoryResponse(**result)
