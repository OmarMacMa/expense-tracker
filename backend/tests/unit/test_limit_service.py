import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.models import Category, Limit
from app.schemas.expense import ExpenseCreate
from app.schemas.limit import (
    LimitCreate,
    LimitFilterCreate,
    LimitFilterResponse,
    LimitUpdate,
)
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


def test_warning_pct_normalizes_excess_precision_on_create():
    """Excess decimal places are rounded to 2 so UI round-trip is lossless.
    E.g., 0.3333 → 0.33 prevents silent corruption when editing a limit."""
    data = LimitCreate(
        name="Precise",
        timeframe="weekly",
        threshold_amount=Decimal("100"),
        warning_pct=Decimal("0.3333"),
    )
    assert data.warning_pct == Decimal("0.33")


def test_warning_pct_normalizes_excess_precision_on_update():
    """LimitUpdate should also normalize precision."""
    data = LimitUpdate(warning_pct=Decimal("0.8567"))
    assert data.warning_pct == Decimal("0.86")


@pytest.mark.asyncio
async def test_limit_category_filter_only_counts_matching(
    db_session, test_user, test_space
):
    """Limit with a category filter should only count expenses in that category."""
    from app.schemas.category import CategoryCreate
    from app.schemas.limit import LimitFilterCreate
    from app.services.category import create_category

    # Create a "Groceries" category
    groceries = await create_category(
        db_session, test_space.id, CategoryCreate(name="Groceries")
    )
    uncat_id = await _get_uncategorized_id(db_session, test_space.id)

    # Create limit filtered to Groceries only
    limit_data = LimitCreate(
        name="Grocery Budget",
        timeframe="monthly",
        threshold_amount=Decimal("200"),
        filters=[
            LimitFilterCreate(filter_type="category", filter_value=str(groceries.id))
        ],
    )
    await create_limit(db_session, test_space.id, limit_data)

    # Expense in Groceries ($60) — should count
    await create_expense(
        db_session,
        test_space.id,
        ExpenseCreate(
            merchant="Supermart",
            purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
            amount=Decimal("60.00"),
            category_id=groceries.id,
            spender_id=test_user.id,
        ),
        test_user.id,
    )

    # Expense in Uncategorized ($40) — should NOT count
    await create_expense(
        db_session,
        test_space.id,
        ExpenseCreate(
            merchant="Random Shop",
            purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
            amount=Decimal("40.00"),
            category_id=uncat_id,
            spender_id=test_user.id,
        ),
        test_user.id,
    )

    limits = await list_limits_with_progress(db_session, test_space.id)
    assert len(limits) == 1
    assert limits[0]["spent"] == Decimal("60.00")
    assert limits[0]["progress"] == Decimal("0.3000")  # 60/200
    assert limits[0]["status"] == "ok"


# ── filter_display_name tests ──


def test_limit_filter_response_has_display_name_field():
    """LimitFilterResponse must expose filter_display_name for UI label resolution."""
    resp = LimitFilterResponse(
        id=uuid.uuid4(),
        filter_type="category",
        filter_value=str(uuid.uuid4()),
        filter_display_name="Groceries",
    )
    assert resp.filter_display_name == "Groceries"


def test_limit_filter_response_display_name_defaults_to_empty():
    """filter_display_name defaults to empty string when not supplied."""
    resp = LimitFilterResponse(
        id=uuid.uuid4(),
        filter_type="category",
        filter_value=str(uuid.uuid4()),
    )
    assert resp.filter_display_name == ""


# ── LimitUpdate.filters schema tests ──


def test_limit_update_accepts_filters_field():
    """LimitUpdate must accept an optional filters list for category replacement."""
    cat_uuid = str(uuid.uuid4())
    data = LimitUpdate(
        filters=[LimitFilterCreate(filter_type="category", filter_value=cat_uuid)]
    )
    assert data.filters is not None
    assert len(data.filters) == 1
    assert data.filters[0].filter_value == cat_uuid


def test_limit_update_filters_defaults_to_none():
    """When not supplied, filters is None (not set → not replaced)."""
    data = LimitUpdate(name="No filter change")
    assert data.filters is None


def test_limit_update_accepts_empty_filters_list():
    """Empty filters list means clear all category filters on edit."""
    data = LimitUpdate(filters=[])
    assert data.filters == []


# ── service-level filter replacement tests (require DB) ──


@pytest.mark.asyncio
async def test_update_limit_replaces_filters(db_session, test_user, test_space):
    """Updating a limit with new filters replaces the old ones entirely."""
    from app.schemas.category import CategoryCreate
    from app.services.category import create_category

    cat_a = await create_category(
        db_session, test_space.id, CategoryCreate(name="Cat A")
    )
    cat_b = await create_category(
        db_session, test_space.id, CategoryCreate(name="Cat B")
    )

    # Create limit initially filtered to Cat A only
    limit = await create_limit(
        db_session,
        test_space.id,
        LimitCreate(
            name="My Limit",
            timeframe="monthly",
            threshold_amount=Decimal("100"),
            filters=[
                LimitFilterCreate(filter_type="category", filter_value=str(cat_a.id))
            ],
        ),
    )

    # Now update to replace filters with Cat B only
    updated = await update_limit(
        db_session,
        test_space.id,
        limit.id,
        LimitUpdate(
            filters=[
                LimitFilterCreate(filter_type="category", filter_value=str(cat_b.id))
            ]
        ),
    )

    # Reload filters
    await db_session.refresh(updated, ["filters"])
    assert len(updated.filters) == 1
    assert updated.filters[0].filter_value == str(cat_b.id)


@pytest.mark.asyncio
async def test_update_limit_clears_filters_when_empty_list(
    db_session, test_user, test_space
):
    """Passing filters=[] removes all category filters from the limit."""
    from app.schemas.category import CategoryCreate
    from app.services.category import create_category

    cat = await create_category(
        db_session, test_space.id, CategoryCreate(name="Dining")
    )

    limit = await create_limit(
        db_session,
        test_space.id,
        LimitCreate(
            name="Dining Budget",
            timeframe="monthly",
            threshold_amount=Decimal("150"),
            filters=[
                LimitFilterCreate(filter_type="category", filter_value=str(cat.id))
            ],
        ),
    )

    updated = await update_limit(
        db_session,
        test_space.id,
        limit.id,
        LimitUpdate(filters=[]),
    )

    await db_session.refresh(updated, ["filters"])
    assert updated.filters == []


@pytest.mark.asyncio
async def test_update_limit_without_filters_field_preserves_existing(
    db_session, test_user, test_space
):
    """PATCH without the filters key must leave existing filters untouched."""
    from app.schemas.category import CategoryCreate
    from app.services.category import create_category

    cat = await create_category(
        db_session, test_space.id, CategoryCreate(name="Travel")
    )

    limit = await create_limit(
        db_session,
        test_space.id,
        LimitCreate(
            name="Travel Budget",
            timeframe="monthly",
            threshold_amount=Decimal("500"),
            filters=[
                LimitFilterCreate(filter_type="category", filter_value=str(cat.id))
            ],
        ),
    )

    # Update only name — filters should be untouched
    updated = await update_limit(
        db_session,
        test_space.id,
        limit.id,
        LimitUpdate(name="Renamed Budget"),
    )

    await db_session.refresh(updated, ["filters"])
    assert len(updated.filters) == 1
    assert updated.filters[0].filter_value == str(cat.id)


@pytest.mark.asyncio
async def test_list_limits_returns_filter_display_name(
    db_session, test_user, test_space
):
    """list_limits_with_progress resolves category UUID to its name in
    filter_display_name."""
    from app.schemas.category import CategoryCreate
    from app.services.category import create_category

    cat = await create_category(
        db_session, test_space.id, CategoryCreate(name="Entertainment")
    )

    await create_limit(
        db_session,
        test_space.id,
        LimitCreate(
            name="Fun Limit",
            timeframe="monthly",
            threshold_amount=Decimal("100"),
            filters=[
                LimitFilterCreate(
                    filter_type="category", filter_value=str(cat.id)
                )
            ],
        ),
    )

    limits = await list_limits_with_progress(db_session, test_space.id)
    assert len(limits) == 1
    filters = limits[0]["filters"]
    assert len(filters) == 1
    assert filters[0]["filter_display_name"] == "Entertainment"
    # filter_value must still hold the UUID (needed by edit form)
    assert filters[0]["filter_value"] == str(cat.id)
