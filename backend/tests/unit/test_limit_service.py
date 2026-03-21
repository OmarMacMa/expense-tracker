from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Category, Limit
from app.schemas.expense import ExpenseCreate
from app.schemas.limit import LimitCreate, LimitUpdate
from app.services.expense import create_expense
from app.services.limit import (
    create_limit,
    delete_limit,
    list_limits_with_progress,
    update_limit,
)


async def _get_uncategorized_id(db, space_id):
    stmt = select(Category).where(
        Category.space_id == space_id, Category.is_system.is_(True)
    )
    result = await db.execute(stmt)
    return result.scalar_one().id


@pytest.mark.asyncio
async def test_create_limit(db_session, test_user, test_space):
    data = LimitCreate(
        name="Weekly Groceries", timeframe="weekly", threshold_amount=Decimal("100")
    )
    limit = await create_limit(db_session, test_space.id, data)
    assert limit.name == "Weekly Groceries"
    assert limit.timeframe == "weekly"
    assert limit.threshold_amount == Decimal("100")


@pytest.mark.asyncio
async def test_create_limit_invalid_timeframe(db_session, test_user, test_space):
    data = LimitCreate(
        name="Bad", timeframe="quarterly", threshold_amount=Decimal("100")
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_limit(db_session, test_space.id, data)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_update_limit(db_session, test_user, test_space):
    data = LimitCreate(
        name="Old Name", timeframe="monthly", threshold_amount=Decimal("500")
    )
    limit = await create_limit(db_session, test_space.id, data)

    updated = await update_limit(
        db_session, test_space.id, limit.id, LimitUpdate(name="New Name")
    )
    assert updated.name == "New Name"
    assert updated.threshold_amount == Decimal("500")  # unchanged


@pytest.mark.asyncio
async def test_delete_limit(db_session, test_user, test_space):
    data = LimitCreate(
        name="ToDelete", timeframe="weekly", threshold_amount=Decimal("100")
    )
    limit = await create_limit(db_session, test_space.id, data)

    await delete_limit(db_session, test_space.id, limit.id)

    stmt = select(Limit).where(Limit.id == limit.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_limit_progress_no_expenses(db_session, test_user, test_space):
    """Limit with no expenses shows zero progress."""
    data = LimitCreate(
        name="Monthly Total", timeframe="monthly", threshold_amount=Decimal("1000")
    )
    await create_limit(db_session, test_space.id, data)

    limits = await list_limits_with_progress(db_session, test_space.id)
    assert len(limits) == 1
    assert limits[0]["spent"] == Decimal("0")
    assert limits[0]["progress"] == Decimal("0")
    assert limits[0]["status"] == "ok"


@pytest.mark.asyncio
async def test_limit_progress_with_expenses(db_session, test_user, test_space):
    """Limit with expenses shows correct progress."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)

    # Create limit
    data = LimitCreate(
        name="Monthly", timeframe="monthly", threshold_amount=Decimal("100")
    )
    await create_limit(db_session, test_space.id, data)

    # Add expense in current month
    expense_data = ExpenseCreate(
        merchant="Store",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("60.00"),
        category_id=cat_id,
        spender_id=test_user.id,
    )
    await create_expense(db_session, test_space.id, expense_data, test_user.id)

    limits = await list_limits_with_progress(db_session, test_space.id)
    assert limits[0]["spent"] == Decimal("60.00")
    assert limits[0]["progress"] == Decimal("0.6000")
    assert limits[0]["status"] == "warning"  # 60% >= warning_pct (0.60)


@pytest.mark.asyncio
async def test_limit_exceeded_status(db_session, test_user, test_space):
    """Limit shows exceeded when over 100%."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)

    data = LimitCreate(
        name="Small", timeframe="monthly", threshold_amount=Decimal("50")
    )
    await create_limit(db_session, test_space.id, data)

    expense_data = ExpenseCreate(
        merchant="Store",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("75.00"),
        category_id=cat_id,
        spender_id=test_user.id,
    )
    await create_expense(db_session, test_space.id, expense_data, test_user.id)

    limits = await list_limits_with_progress(db_session, test_space.id)
    assert limits[0]["status"] == "exceeded"
    assert limits[0]["progress"] > Decimal("1")
