from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.models import Category, Limit
from app.schemas.category import CategoryCreate
from app.schemas.expense import ExpenseCreate
from app.schemas.limit import LimitCreate, LimitUpdate
from app.services.category import create_category
from app.services.expense import create_expense
from app.services.limit import (
    create_limit,
    delete_limit,
    list_limits_with_progress,
    update_limit,
)
from app.services.time_window import TimeWindowResolver


async def _get_uncategorized_id(db, space_id):
    stmt = select(Category).where(
        Category.space_id == space_id, Category.is_system.is_(True)
    )
    result = await db.execute(stmt)
    return result.scalar_one().id


def _mid_window_timestamp(timeframe: str = "monthly") -> datetime:
    """Return a UTC timestamp safely in the middle of the current time window."""
    resolver = TimeWindowResolver("UTC")
    start_utc, end_utc = resolver.get_current_window(timeframe)
    return start_utc + (end_utc - start_utc) / 2


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


# ── Schema-level validation tests ──


def test_limit_create_rejects_warning_pct_over_1():
    """warning_pct is a 0-1 decimal fraction; values > 1 are invalid."""
    with pytest.raises(ValidationError):
        LimitCreate(
            name="Bad",
            timeframe="weekly",
            threshold_amount=Decimal("100"),
            warning_pct=Decimal("1.01"),
        )


def test_limit_create_rejects_negative_warning_pct():
    """Negative percentages are invalid."""
    with pytest.raises(ValidationError):
        LimitCreate(
            name="Bad",
            timeframe="weekly",
            threshold_amount=Decimal("100"),
            warning_pct=Decimal("-0.01"),
        )


def test_limit_create_accepts_decimal_warning_pct():
    """Frontend must send warning_pct as a 0-1 decimal (e.g. 0.60 for 60%)."""
    data = LimitCreate(
        name="Weekly Budget",
        timeframe="weekly",
        threshold_amount=Decimal("200"),
        warning_pct=Decimal("0.60"),
    )
    assert data.warning_pct == Decimal("0.60")


def test_limit_create_accepts_boundary_1():
    """warning_pct=1 (100% threshold) is valid."""
    data = LimitCreate(
        name="Strict",
        timeframe="monthly",
        threshold_amount=Decimal("500"),
        warning_pct=Decimal("1"),
    )
    assert data.warning_pct == Decimal("1")


def test_limit_create_default_warning_pct():
    """Default warning_pct should be 0.6 (i.e. 60%)."""
    data = LimitCreate(
        name="Default",
        timeframe="monthly",
        threshold_amount=Decimal("300"),
    )
    assert data.warning_pct == Decimal("0.6000")


def test_limit_update_accepts_decimal_warning_pct():
    """LimitUpdate should accept 0-1 range."""
    data = LimitUpdate(warning_pct=Decimal("0.75"))
    assert data.warning_pct == Decimal("0.75")


# ── Category-filter tests ──


@pytest.mark.asyncio
async def test_limit_with_category_filter_excludes_other_categories(
    db_session, test_user, test_space
):
    """A limit with a category filter must only count expenses in that category."""
    # Create two categories
    groceries = await create_category(
        db_session, test_space.id, CategoryCreate(name="Groceries")
    )
    dining = await create_category(
        db_session, test_space.id, CategoryCreate(name="Dining")
    )

    # Limit scoped to Groceries only
    limit_data = LimitCreate(
        name="Grocery Budget",
        timeframe="monthly",
        threshold_amount=Decimal("200"),
        filters=[
            {"filter_type": "category", "filter_value": str(groceries.id)},
        ],
    )
    await create_limit(db_session, test_space.id, limit_data)

    # Add an expense in the Dining category (should NOT count)
    await create_expense(
        db_session,
        test_space.id,
        ExpenseCreate(
            merchant="Restaurant",
            purchase_datetime=_mid_window_timestamp(),
            amount=Decimal("80.00"),
            category_id=dining.id,
            spender_id=test_user.id,
        ),
        test_user.id,
    )

    limits = await list_limits_with_progress(db_session, test_space.id)
    grocery_limit = [lim for lim in limits if lim["name"] == "Grocery Budget"][0]

    # Dining expense should be excluded → spent must be 0
    assert grocery_limit["spent"] == Decimal("0")
    assert grocery_limit["progress"] == Decimal("0")
    assert grocery_limit["status"] == "ok"


@pytest.mark.asyncio
async def test_limit_with_category_filter_includes_only_matching_expenses(
    db_session, test_user, test_space
):
    """Expenses in the matching category are counted; others are ignored."""
    groceries = await create_category(
        db_session, test_space.id, CategoryCreate(name="Groceries")
    )
    dining = await create_category(
        db_session, test_space.id, CategoryCreate(name="Dining")
    )

    limit_data = LimitCreate(
        name="Grocery Budget",
        timeframe="monthly",
        threshold_amount=Decimal("200"),
        filters=[
            {"filter_type": "category", "filter_value": str(groceries.id)},
        ],
    )
    await create_limit(db_session, test_space.id, limit_data)

    mid_window = _mid_window_timestamp()

    # Expense in Groceries (should count)
    await create_expense(
        db_session,
        test_space.id,
        ExpenseCreate(
            merchant="Supermarket",
            purchase_datetime=mid_window,
            amount=Decimal("50.00"),
            category_id=groceries.id,
            spender_id=test_user.id,
        ),
        test_user.id,
    )

    # Expense in Dining (should NOT count)
    await create_expense(
        db_session,
        test_space.id,
        ExpenseCreate(
            merchant="Restaurant",
            purchase_datetime=mid_window,
            amount=Decimal("70.00"),
            category_id=dining.id,
            spender_id=test_user.id,
        ),
        test_user.id,
    )

    limits = await list_limits_with_progress(db_session, test_space.id)
    grocery_limit = [lim for lim in limits if lim["name"] == "Grocery Budget"][0]

    # Only the $50 grocery expense should count
    assert grocery_limit["spent"] == Decimal("50.00")
    assert grocery_limit["progress"] == Decimal("0.2500")
    assert grocery_limit["status"] == "ok"


@pytest.mark.asyncio
async def test_update_limit_filters(db_session, test_user, test_space):
    """Updating filters replaces old filters with new ones."""
    groceries = await create_category(
        db_session, test_space.id, CategoryCreate(name="Groceries")
    )
    dining = await create_category(
        db_session, test_space.id, CategoryCreate(name="Dining")
    )

    # Create limit scoped to Groceries
    limit_data = LimitCreate(
        name="Food Budget",
        timeframe="monthly",
        threshold_amount=Decimal("300"),
        filters=[
            {"filter_type": "category", "filter_value": str(groceries.id)},
        ],
    )
    limit = await create_limit(db_session, test_space.id, limit_data)

    mid_window = _mid_window_timestamp()

    # Add expense in Dining
    await create_expense(
        db_session,
        test_space.id,
        ExpenseCreate(
            merchant="Restaurant",
            purchase_datetime=mid_window,
            amount=Decimal("90.00"),
            category_id=dining.id,
            spender_id=test_user.id,
        ),
        test_user.id,
    )

    # Before update: Dining expense should NOT count (filter is Groceries)
    limits = await list_limits_with_progress(db_session, test_space.id)
    food_limit = [lim for lim in limits if lim["name"] == "Food Budget"][0]
    assert food_limit["spent"] == Decimal("0")

    # Update filter from Groceries → Dining
    await update_limit(
        db_session,
        test_space.id,
        limit.id,
        LimitUpdate(
            filters=[
                {"filter_type": "category", "filter_value": str(dining.id)},
            ]
        ),
    )

    # After update: Dining expense SHOULD count now
    limits = await list_limits_with_progress(db_session, test_space.id)
    food_limit = [lim for lim in limits if lim["name"] == "Food Budget"][0]
    assert food_limit["spent"] == Decimal("90.00")
    assert food_limit["progress"] == Decimal("0.3000")


@pytest.mark.asyncio
async def test_update_limit_clear_filters(db_session, test_user, test_space):
    """Sending an empty filters list removes all category filters."""
    groceries = await create_category(
        db_session, test_space.id, CategoryCreate(name="Groceries")
    )

    limit_data = LimitCreate(
        name="Scoped Limit",
        timeframe="monthly",
        threshold_amount=Decimal("500"),
        filters=[
            {"filter_type": "category", "filter_value": str(groceries.id)},
        ],
    )
    limit = await create_limit(db_session, test_space.id, limit_data)

    # Verify filter was created
    limits = await list_limits_with_progress(db_session, test_space.id)
    assert len(limits[0]["filters"]) == 1

    # Clear filters
    await update_limit(
        db_session,
        test_space.id,
        limit.id,
        LimitUpdate(filters=[]),
    )

    # After update: no filters remain
    limits = await list_limits_with_progress(db_session, test_space.id)
    scoped_limit = [lim for lim in limits if lim["name"] == "Scoped Limit"][0]
    assert len(scoped_limit["filters"]) == 0
