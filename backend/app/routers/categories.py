import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.space import get_current_space_member
from app.models import SpaceMember
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.category import (
    create_category,
    delete_category,
    list_categories,
    update_category,
)

router = APIRouter(prefix="/api/v1/spaces/{space_id}", tags=["categories"])


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories_endpoint(
    space_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryResponse]:
    categories = await list_categories(db, space_id)
    return [CategoryResponse.model_validate(c) for c in categories]


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category_endpoint(
    space_id: uuid.UUID,
    data: CategoryCreate,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    category = await create_category(db, space_id, data)
    return CategoryResponse.model_validate(category)


@router.put("/categories/{cat_id}", response_model=CategoryResponse)
async def update_category_endpoint(
    space_id: uuid.UUID,
    cat_id: uuid.UUID,
    data: CategoryUpdate,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> CategoryResponse:
    category = await update_category(db, space_id, cat_id, data)
    return CategoryResponse.model_validate(category)


@router.delete("/categories/{cat_id}", status_code=204)
async def delete_category_endpoint(
    space_id: uuid.UUID,
    cat_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    await delete_category(db, space_id, cat_id)
