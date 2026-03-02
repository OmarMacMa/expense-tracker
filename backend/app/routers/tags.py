import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.space import get_current_space_member
from app.models import SpaceMember
from app.schemas.tag import TagResponse
from app.services.tag import list_tags

router = APIRouter(prefix="/api/v1/spaces/{space_id}", tags=["tags"])


@router.get("/tags", response_model=list[TagResponse])
async def list_tags_endpoint(
    space_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[TagResponse]:
    """List all tags in a space for autocomplete."""
    tags = await list_tags(db, space_id)
    return [TagResponse.model_validate(t) for t in tags]
