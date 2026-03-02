import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.models import SpaceMember, User


async def get_current_space_member(
    space_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpaceMember:
    """Verify the current user is a member of the specified space.

    Returns the SpaceMember record. Raises 403 if not a member.
    """
    stmt = select(SpaceMember).where(
        SpaceMember.space_id == space_id,
        SpaceMember.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {"code": "FORBIDDEN", "message": "Not a member of this space"}
            },
        )

    return member
