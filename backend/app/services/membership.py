"""Transaction-local membership primitives; callers own commit/rollback."""

import uuid

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Category,
    Expense,
    ExpenseLine,
    InviteLink,
    Limit,
    LimitFilter,
    Merchant,
    MonthlyWrap,
    PaymentMethod,
    RecurringTemplate,
    Space,
    SpaceMember,
    Tag,
    User,
)
from app.models.expense import expense_line_tags
from app.schemas.space import LeaveConfirmation, LeavePreview

SPACE_DATA = (
    Expense,
    RecurringTemplate,
    Merchant,
    MonthlyWrap,
    Limit,
    Tag,
    Category,
    PaymentMethod,
    InviteLink,
)


def conflict(code: str, message: str, status: int = 409) -> HTTPException:
    """Keep the existing business-error envelope."""
    return HTTPException(
        status_code=status, detail={"error": {"code": code, "message": message}}
    )


async def lock_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Serialize all membership transitions for the acting account."""
    # NO KEY UPDATE still serializes transitions but allows expense/owner FK
    # checks, avoiding a cycle between their space lock and this account lock.
    user = await db.scalar(
        select(User).where(User.id == user_id).with_for_update(key_share=True)
    )
    if user is None:
        raise conflict("NOT_FOUND", "Account not found", 404)


async def lock_spaces(
    db: AsyncSession, space_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Space]:
    """Use the same deterministic order for opposing transfers and joins."""
    spaces = {}
    for space_id in sorted(set(space_ids)):
        space = await db.scalar(
            select(Space)
            .where(Space.id == space_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if space is not None:
            spaces[space.id] = space
    return spaces


async def memberships(db: AsyncSession, user_id: uuid.UUID) -> list[SpaceMember]:
    """Read authoritative memberships after locking the acting user."""
    return list(
        await db.scalars(select(SpaceMember).where(SpaceMember.user_id == user_id))
    )


async def leave_preview(
    db: AsyncSession, space_id: uuid.UUID, user_id: uuid.UUID
) -> LeavePreview:
    """Count all source data, including dormant features and pending expenses."""
    space = await db.get(Space, space_id, populate_existing=True)
    member_ids = list(
        await db.scalars(
            select(SpaceMember.user_id)
            .where(SpaceMember.space_id == space_id)
            .order_by(SpaceMember.user_id)
        )
    )
    if space is None or user_id not in member_ids:
        raise conflict("NOT_FOUND", "Space membership not found", 404)
    counts = {}
    for model in SPACE_DATA:
        counts[model.__tablename__] = await db.scalar(
            select(func.count()).select_from(model).where(model.space_id == space_id)
        )
    line_ids = select(ExpenseLine.id).join(Expense).where(Expense.space_id == space_id)
    counts["expense_lines"] = await db.scalar(
        select(func.count())
        .select_from(ExpenseLine)
        .where(ExpenseLine.id.in_(line_ids))
    )
    counts["expense_line_tags"] = await db.scalar(
        select(func.count())
        .select_from(expense_line_tags)
        .where(expense_line_tags.c.expense_line_id.in_(line_ids))
    )
    counts["limit_filters"] = await db.scalar(
        select(func.count())
        .select_from(LimitFilter)
        .where(
            LimitFilter.limit_id.in_(select(Limit.id).where(Limit.space_id == space_id))
        )
    )
    return LeavePreview(
        space_id=space_id,
        space_name=space.name,
        member_ids=member_ids,
        member_count=len(member_ids),
        source_deleted=len(member_ids) == 1,
        counts=counts,
    )


async def confirm_leave(
    db: AsyncSession,
    space_id: uuid.UUID,
    user_id: uuid.UUID,
    confirmation: LeaveConfirmation,
) -> LeavePreview:
    """Reject a changed warning rather than silently deleting different data."""
    current = await leave_preview(db, space_id, user_id)
    if confirmation.source_name != current.space_name:
        raise conflict(
            "CONFIRMATION_MISMATCH", "Type the exact current space name", 422
        )
    if confirmation.preview != current:
        raise conflict(
            "PREVIEW_CHANGED", "Space contents or membership changed. Review again."
        )
    return current


async def remove_source(
    db: AsyncSession, space_id: uuid.UUID, user_id: uuid.UUID, source_deleted: bool
) -> None:
    """Remove only the actor; explicitly clean every owned table if empty."""
    await db.execute(
        delete(SpaceMember).where(
            SpaceMember.space_id == space_id, SpaceMember.user_id == user_id
        )
    )
    if source_deleted:
        for model in SPACE_DATA:
            await db.execute(delete(model).where(model.space_id == space_id))
        await db.execute(delete(SpaceMember).where(SpaceMember.space_id == space_id))
        await db.execute(delete(Space).where(Space.id == space_id))
