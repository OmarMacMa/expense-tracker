import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.space import get_current_space_member
from app.models import SpaceMember
from app.schemas.limit import LimitCreate, LimitResponse, LimitUpdate
from app.services.limit import (
    create_limit,
    delete_limit,
    list_limits_with_progress,
    update_limit,
)

router = APIRouter(prefix="/api/v1/spaces/{space_id}", tags=["limits"])


@router.get("/limits", response_model=list[LimitResponse])
async def list_limits_endpoint(
    space_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[LimitResponse]:
    """List all limits with current progress."""
    limits = await list_limits_with_progress(db, space_id)
    return [LimitResponse(**lim) for lim in limits]


@router.post("/limits", response_model=LimitResponse, status_code=201)
async def create_limit_endpoint(
    space_id: uuid.UUID,
    data: LimitCreate,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> LimitResponse:
    """Create a spending limit."""
    limit = await create_limit(db, space_id, data)
    # Re-fetch with progress
    limits = await list_limits_with_progress(db, space_id)
    for lim in limits:
        if lim["id"] == limit.id:
            return LimitResponse(**lim)
    return LimitResponse(**limits[-1])  # fallback


@router.patch("/limits/{limit_id}", response_model=LimitResponse)
async def update_limit_endpoint(
    space_id: uuid.UUID,
    limit_id: uuid.UUID,
    data: LimitUpdate,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> LimitResponse:
    """Partial update a limit."""
    await update_limit(db, space_id, limit_id, data)
    # Re-fetch with progress
    limits = await list_limits_with_progress(db, space_id)
    for lim in limits:
        if lim["id"] == limit_id:
            return LimitResponse(**lim)
    raise  # should not reach here


@router.delete("/limits/{limit_id}", status_code=204)
async def delete_limit_endpoint(
    space_id: uuid.UUID,
    limit_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a limit."""
    await delete_limit(db, space_id, limit_id)
