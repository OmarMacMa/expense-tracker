import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InviteLink, Space, SpaceMember
from app.services.membership import conflict, lock_spaces, lock_user
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


async def preview_invite(
    db: AsyncSession, token: str, user_id: uuid.UUID | None = None
) -> dict:
    """Return the target space info for an invite without consuming it.

    Reports authoritative target membership and capacity. Existing target
    members may open a consumed/expired link to reach their dashboard; this
    never makes the invitation reusable.
    """
    stmt = select(InviteLink).where(InviteLink.token == token)
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Invite link not found"}},
        )

    target_member = (
        await db.scalar(
            select(SpaceMember).where(
                SpaceMember.space_id == invite.space_id, SpaceMember.user_id == user_id
            )
        )
        if user_id
        else None
    )

    if invite.expires_at <= datetime.now(UTC) and target_member is None:
        raise HTTPException(
            status_code=410,
            detail={
                "error": {
                    "code": "INVITE_EXPIRED",
                    "message": "This invite link has expired",
                }
            },
        )

    if invite.used_at is not None and target_member is None:
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
    space = (await db.execute(space_stmt)).scalar_one_or_none()
    if space is None:
        raise conflict("NOT_FOUND", "Invited space no longer exists", 404)

    return {
        "space_id": space.id,
        "space_name": space.name,
        "space_currency_code": space.currency_code,
        "already_member": target_member is not None,
        "member_count": await get_member_count(db, space.id),
        "max_members": MAX_MEMBERS,
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
    await lock_user(db, user_id)
    # Discover the destination before taking ordered space locks; re-read the
    # invitation under its lock afterward in case the destination was deleted.
    stmt = select(InviteLink).where(InviteLink.token == token)
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Invite link not found"}},
        )

    spaces = await lock_spaces(db, [invite.space_id])
    if invite.space_id not in spaces:
        raise conflict("NOT_FOUND", "Invited space no longer exists", 404)
    invite = await db.scalar(
        select(InviteLink)
        .where(InviteLink.token == token)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if invite is None:
        raise conflict("NOT_FOUND", "Invite link not found", 404)

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

    await validate_destination(db, invite)

    # Add user as member
    new_member = SpaceMember(space_id=invite.space_id, user_id=user_id)
    db.add(new_member)

    # Mark invite as used
    invite.used_at = datetime.now(UTC)
    invite.used_by = user_id

    space = spaces[invite.space_id]
    space_id, space_name = space.id, space.name
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "space_id": space_id,
        "space_name": space_name,
        "message": f"Successfully joined {space_name}",
    }


async def validate_destination(db: AsyncSession, invite: InviteLink) -> None:
    """Revalidate a locked invitation and destination before any source mutation."""
    if invite.expires_at <= datetime.now(UTC):
        raise conflict("INVITE_EXPIRED", "This invite link has expired", 410)
    if invite.used_at is not None:
        raise conflict("INVITE_USED", "This invite link has already been used", 410)
    if await get_member_count(db, invite.space_id) >= MAX_MEMBERS:
        raise conflict("MEMBER_LIMIT", "This space has reached its member limit (10).")
