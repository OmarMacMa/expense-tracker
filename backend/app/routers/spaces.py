import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.middleware.space import get_current_space_member
from app.models import SpaceMember, User
from app.schemas.invite import InvitePreviewResponse, InviteResponse, JoinResponse
from app.schemas.space import MemberResponse, SpaceCreate, SpaceResponse, SpaceUpdate
from app.services.invite import generate_invite, join_space, preview_invite
from app.services.space import create_space, get_space, list_members, update_space

router = APIRouter(prefix="/api/v1", tags=["spaces"])


@router.post("/spaces", response_model=SpaceResponse, status_code=201)
async def create_space_endpoint(
    data: SpaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """Create a new space. The creator is automatically added as a member."""
    space = await create_space(db, current_user, data)
    return SpaceResponse.model_validate(space)


@router.get(
    "/spaces/invites/{invite_token}/preview",
    response_model=InvitePreviewResponse,
)
async def preview_invite_endpoint(
    invite_token: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitePreviewResponse:
    """Preview an invite (target space info) without consuming it.

    Requires auth (so we don't leak space names to unauthenticated probes),
    but does NOT require membership in any space — the frontend uses this on
    /join/:token after the user signs in, to render a confirmation step
    showing which space they're about to join.
    """
    result = await preview_invite(db, invite_token)
    return InvitePreviewResponse(**result)


@router.post("/spaces/join/{invite_token}", response_model=JoinResponse)
async def join_space_endpoint(
    invite_token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JoinResponse:
    """Join a space via invite token. Requires auth but NOT space membership."""
    result = await join_space(db, invite_token, current_user.id)
    return JoinResponse(**result)


@router.get("/spaces/{space_id}", response_model=SpaceResponse)
async def get_space_endpoint(
    space_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """Get space details. Requires space membership."""
    space = await get_space(db, space_id)
    if space is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Space not found"}},
        )
    return SpaceResponse.model_validate(space)


@router.put("/spaces/{space_id}", response_model=SpaceResponse)
async def update_space_endpoint(
    space_id: uuid.UUID,
    data: SpaceUpdate,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """Update space settings. Currency is immutable."""
    space = await update_space(db, space_id, data)
    if space is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Space not found"}},
        )
    return SpaceResponse.model_validate(space)


@router.get("/spaces/{space_id}/members", response_model=list[MemberResponse])
async def list_members_endpoint(
    space_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    """List space members with user info."""
    members = await list_members(db, space_id)
    return [MemberResponse(**m) for m in members]


@router.post(
    "/spaces/{space_id}/invite", response_model=InviteResponse, status_code=201
)
async def generate_invite_endpoint(
    space_id: uuid.UUID,
    member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> InviteResponse:
    """Generate a single-use invite link. Requires space membership."""
    invite = await generate_invite(db, space_id, member.user_id)
    return InviteResponse.model_validate(invite)
