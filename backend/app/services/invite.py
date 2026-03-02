import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InviteLink, Space, SpaceMember
from app.services.space import MAX_MEMBERS, get_member_count

INVITE_EXPIRY_DAYS = 7


async def generate_invite(
    db: AsyncSession, space_id: uuid.UUID, created_by: uuid.UUID
) -> InviteLink:
    """Generate a single-use invite link with 7-day expiry."""
    invite = InviteLink(
        space_id=space_id,
        token=secrets.token_urlsafe(32),
        created_by=created_by,
        expires_at=datetime.now(UTC) + timedelta(days=INVITE_EXPIRY_DAYS),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def join_space(db: AsyncSession, token: str, user_id: uuid.UUID) -> dict:
    """Join a space via invite token.

    Validates: token exists, not expired, not used, space not at limit,
    user not already member.
    Returns dict with space_id, space_name, message.
    """
    # Find invite by token
    stmt = select(InviteLink).where(InviteLink.token == token)
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Invite link not found"}},
        )

    # Check if expired
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=410,
            detail={
                "error": {
                    "code": "INVITE_EXPIRED",
                    "message": "This invite link has expired",
                }
            },
        )

    # Check if already used
    if invite.used_at is not None:
        raise HTTPException(
            status_code=410,
            detail={
                "error": {
                    "code": "INVITE_USED",
                    "message": "This invite link has already been used",
                }
            },
        )

    # Check member limit
    member_count = await get_member_count(db, invite.space_id)
    if member_count >= MAX_MEMBERS:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "MEMBER_LIMIT",
                    "message": "This space has reached its member limit (10).",
                }
            },
        )

    # Check if user is already a member
    existing_stmt = select(SpaceMember).where(
        SpaceMember.space_id == invite.space_id,
        SpaceMember.user_id == user_id,
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "ALREADY_MEMBER",
                    "message": "Already a member of this space",
                }
            },
        )

    # Add user as member
    new_member = SpaceMember(space_id=invite.space_id, user_id=user_id)
    db.add(new_member)

    # Mark invite as used
    invite.used_at = datetime.now(UTC)
    invite.used_by = user_id

    await db.commit()

    # Get space name for response
    space_stmt = select(Space).where(Space.id == invite.space_id)
    space_result = await db.execute(space_stmt)
    space = space_result.scalar_one()

    return {
        "space_id": space.id,
        "space_name": space.name,
        "message": f"Successfully joined {space.name}",
    }
