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


async def preview_invite(db: AsyncSession, token: str) -> dict:
    """Return the target space info for an invite without consuming it.

    Validates that the invite exists, is not expired, and is not used.
    Does NOT check user membership state — the frontend decides what to do
    with that information. Used by the frontend confirmation step before
    calling join_space().
    """
    stmt = select(InviteLink).where(InviteLink.token == token)
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Invite link not found"}},
        )

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

    space_stmt = select(Space).where(Space.id == invite.space_id)
    space = (await db.execute(space_stmt)).scalar_one()

    return {
        "space_id": space.id,
        "space_name": space.name,
        "space_currency_code": space.currency_code,
    }


async def join_space(db: AsyncSession, token: str, user_id: uuid.UUID) -> dict:
    """Join a space via invite token.

    Validation order (user-state errors before space-state errors):
      1. Invite token exists (404)
      2. User is already a member of the target space (409 ALREADY_MEMBER)
      3. User already belongs to some OTHER space (409 ALREADY_HAS_SPACE)
      4. Invite expired (410)
      5. Invite already used (410)
      6. Target space at member limit (409)

    Returns dict with space_id, space_name, message.
    """
    # 1. Find invite by token
    stmt = select(InviteLink).where(InviteLink.token == token)
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Invite link not found"}},
        )

    # 2. Target-space membership check (deterministic when target matches).
    # Uses .scalars().first() rather than scalar_one_or_none() to tolerate any
    # historical multi-membership data that may exist from prior bugs.
    target_member_stmt = (
        select(SpaceMember)
        .where(
            SpaceMember.space_id == invite.space_id,
            SpaceMember.user_id == user_id,
        )
        .limit(1)
    )
    target_member = (await db.execute(target_member_stmt)).scalars().first()
    if target_member is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "ALREADY_MEMBER",
                    "message": "Already a member of this space",
                }
            },
        )

    # 3. Any-space membership (one-space-per-user invariant).
    any_space_stmt = select(SpaceMember).where(SpaceMember.user_id == user_id).limit(1)
    any_existing = (await db.execute(any_space_stmt)).scalars().first()
    if any_existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "ALREADY_HAS_SPACE",
                    "message": "You already belong to a space. "
                    "Leave your current space before joining another.",
                }
            },
        )

    # 4. Check if expired
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

    # 5. Check if already used
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

    # 6. Check member limit
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
