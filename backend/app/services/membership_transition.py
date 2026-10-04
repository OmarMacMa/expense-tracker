import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InviteLink, SpaceMember
from app.schemas.space import LeaveConfirmation, MembershipOutcome, MembershipTransfer
from app.services.invite import validate_destination
from app.services.membership import (
    confirm_leave,
    conflict,
    lock_spaces,
    lock_user,
    memberships,
    remove_source,
)

logger = structlog.get_logger()


async def leave_space(
    db: AsyncSession,
    space_id: uuid.UUID,
    user_id: uuid.UUID,
    data: LeaveConfirmation,
) -> MembershipOutcome:
    """Commit self-leave and optional empty-space deletion atomically."""
    try:
        await lock_user(db, user_id)
        await lock_spaces(db, [space_id])
        preview = await confirm_leave(db, space_id, user_id, data)
        await remove_source(db, space_id, user_id, preview.source_deleted)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    logger.info(
        "space_left",
        user_id=str(user_id),
        source_space_id=str(space_id),
        source_deleted=preview.source_deleted,
    )
    return MembershipOutcome(
        source_space_id=space_id, source_deleted=preview.source_deleted
    )


async def transfer_membership(
    db: AsyncSession,
    space_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MembershipTransfer,
) -> MembershipOutcome:
    """Leave and accept the intended invitation in one transaction, or do neither."""
    try:
        await lock_user(db, user_id)
        current = await memberships(db, user_id)
        if not any(member.space_id == space_id for member in current):
            raise conflict("NOT_FOUND", "Space membership not found", 404)
        if len(current) != 1:
            raise conflict(
                "ALREADY_HAS_SPACE", "Resolve other memberships before switching."
            )
        invite = await db.scalar(
            select(InviteLink).where(InviteLink.token == data.invite_token)
        )
        if invite is None:
            raise conflict("NOT_FOUND", "Invite link not found", 404)
        destination_id = invite.space_id
        if destination_id == space_id:
            raise conflict("ALREADY_MEMBER", "Already a member of this space")
        spaces = await lock_spaces(db, [space_id, destination_id])
        preview = await confirm_leave(db, space_id, user_id, data)
        if destination_id not in spaces:
            raise conflict("NOT_FOUND", "Invited space no longer exists", 404)
        invite = await db.scalar(
            select(InviteLink)
            .where(InviteLink.token == data.invite_token)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if invite is None:
            raise conflict("NOT_FOUND", "Invite link not found", 404)
        await validate_destination(db, invite)
        destination_name = spaces[destination_id].name
        await remove_source(db, space_id, user_id, preview.source_deleted)
        db.add(SpaceMember(space_id=destination_id, user_id=user_id))
        invite.used_at = datetime.now(UTC)
        invite.used_by = user_id
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    logger.info(
        "membership_transferred",
        user_id=str(user_id),
        source_space_id=str(space_id),
        destination_space_id=str(destination_id),
        source_deleted=preview.source_deleted,
    )
    return MembershipOutcome(
        source_space_id=space_id,
        source_deleted=preview.source_deleted,
        destination_space_id=destination_id,
        destination_space_name=destination_name,
    )
