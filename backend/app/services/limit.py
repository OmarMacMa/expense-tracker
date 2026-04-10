import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Category, Expense, ExpenseLine, Limit, LimitFilter, Space
from app.services.time_window import TimeWindowResolver

VALID_TIMEFRAMES_MVP = {"weekly", "monthly"}


async def create_limit(db: AsyncSession, space_id: uuid.UUID, data) -> Limit:
    """Create a limit with optional category filters."""
    if data.timeframe not in VALID_TIMEFRAMES_MVP:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_TIMEFRAME",
                    "message": "MVP supports weekly and monthly only",
                }
            },
        )

    limit = Limit(
        space_id=space_id,
        name=data.name,
        timeframe=data.timeframe,
        threshold_amount=data.threshold_amount,
        warning_pct=data.warning_pct,
    )
    db.add(limit)
    await db.flush()

    for f in data.filters:
        lf = LimitFilter(
            limit_id=limit.id,
            filter_type=f.filter_type,
            filter_value=f.filter_value,
        )
        db.add(lf)

    await db.commit()
    await db.refresh(limit)
    return limit


async def list_limits_with_progress(
    db: AsyncSession, space_id: uuid.UUID
) -> list[dict]:
    """List all limits with computed progress."""
    space_stmt = select(Space).where(Space.id == space_id)
    space_result = await db.execute(space_stmt)
    space = space_result.scalar_one()

    resolver = TimeWindowResolver(space.timezone)

    stmt = (
        select(Limit)
        .options(selectinload(Limit.filters))
        .where(Limit.space_id == space_id)
        .order_by(Limit.created_at)
    )
    result = await db.execute(stmt)
    limits = result.scalars().all()

    # Collect all category UUIDs referenced by filters so we can resolve them
    # to display names in a single query.
    all_category_ids: set[uuid.UUID] = set()
    for limit in limits:
        for f in limit.filters:
            if f.filter_type == "category":
                uid = _try_parse_uuid(f.filter_value)
                if uid is not None:
                    all_category_ids.add(uid)

    category_names: dict[uuid.UUID, str] = {}
    if all_category_ids:
        cat_stmt = select(Category).where(
            Category.id.in_(all_category_ids),
            Category.space_id == space_id,
        )
        cat_result = await db.execute(cat_stmt)
        for cat in cat_result.scalars().all():
            category_names[cat.id] = cat.name

    results = []
    for limit in limits:
        progress_data = await _calculate_progress(db, space_id, limit, resolver)
        results.append(
            {
                "id": limit.id,
                "name": limit.name,
                "timeframe": limit.timeframe,
                "threshold_amount": limit.threshold_amount,
                "warning_pct": limit.warning_pct,
                "filters": [
                    {
                        "id": f.id,
                        "filter_type": f.filter_type,
                        "filter_value": f.filter_value,
                        "filter_display_name": (
                            category_names.get(
                                _try_parse_uuid(f.filter_value), ""
                            )
                            if f.filter_type == "category"
                            else f.filter_value
                        ),
                    }
                    for f in limit.filters
                ],
                "created_at": limit.created_at,
                **progress_data,
            }
        )

    return results


async def update_limit(
    db: AsyncSession, space_id: uuid.UUID, limit_id: uuid.UUID, data
) -> Limit:
    """Partial update a limit.

    When ``filters`` is supplied (even as an empty list), all existing
    LimitFilter rows are deleted and replaced with the new set.  If
    ``filters`` is absent from the payload the existing filters are left
    untouched.
    """
    limit = await _get_limit(db, space_id, limit_id)
    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data:
        limit.name = update_data["name"]
    if "threshold_amount" in update_data:
        limit.threshold_amount = update_data["threshold_amount"]
    if "warning_pct" in update_data:
        limit.warning_pct = update_data["warning_pct"]

    if "filters" in update_data:
        # Delete existing filters then insert replacements within the same tx.
        from sqlalchemy import delete as sa_delete

        await db.execute(
            sa_delete(LimitFilter).where(LimitFilter.limit_id == limit_id)
        )
        for f in update_data["filters"]:
            db.add(
                LimitFilter(
                    limit_id=limit_id,
                    filter_type=f["filter_type"],
                    filter_value=f["filter_value"],
                )
            )

    await db.commit()
    await db.refresh(limit)
    return limit


async def delete_limit(
    db: AsyncSession, space_id: uuid.UUID, limit_id: uuid.UUID
) -> None:
    """Delete a limit. CASCADE handles filters."""
    limit = await _get_limit(db, space_id, limit_id)
    await db.delete(limit)
    await db.commit()


async def _get_limit(
    db: AsyncSession, space_id: uuid.UUID, limit_id: uuid.UUID
) -> Limit:
    """Get limit by ID within space. Raises 404."""
    stmt = select(Limit).where(Limit.space_id == space_id, Limit.id == limit_id)
    result = await db.execute(stmt)
    limit = result.scalar_one_or_none()
    if limit is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Limit not found"}},
        )
    return limit


async def _calculate_progress(
    db: AsyncSession,
    space_id: uuid.UUID,
    limit: Limit,
    resolver: TimeWindowResolver,
) -> dict:
    """Calculate limit progress: spent, progress ratio, days_remaining, status."""
    start_utc, end_utc = resolver.get_current_window(limit.timeframe)

    # Sum confirmed expense lines in current window
    amount_query = (
        select(func.coalesce(func.sum(ExpenseLine.amount), Decimal("0")))
        .join(Expense, ExpenseLine.expense_id == Expense.id)
        .where(
            Expense.space_id == space_id,
            Expense.status == "confirmed",
            Expense.purchase_datetime >= start_utc,
            Expense.purchase_datetime <= end_utc,
        )
    )

    # Apply category filters if any
    category_filters = [f for f in limit.filters if f.filter_type == "category"]
    if category_filters:
        category_ids = [
            uid
            for f in category_filters
            if (uid := _try_parse_uuid(f.filter_value)) is not None
        ]
        amount_query = amount_query.where(ExpenseLine.category_id.in_(category_ids))

    result = await db.execute(amount_query)
    spent = result.scalar_one() or Decimal("0")

    progress = (
        spent / limit.threshold_amount if limit.threshold_amount > 0 else Decimal("0")
    )

    now = datetime.now(UTC)
    days_remaining = max(0, (end_utc - now).days)

    if progress > Decimal("1"):
        status = "exceeded"
    elif progress >= Decimal("0.9"):
        status = "critical"
    elif progress >= limit.warning_pct:
        status = "warning"
    else:
        status = "ok"

    return {
        "spent": spent,
        "progress": round(progress, 4),
        "days_remaining": days_remaining,
        "status": status,
    }


def _try_parse_uuid(value: str) -> uuid.UUID | None:
    """Return parsed UUID or None if the string is not a valid UUID."""
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
