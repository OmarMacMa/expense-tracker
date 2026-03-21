from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Category
from app.schemas.expense import ExpenseCreate
from app.services.expense import create_expense
from app.services.insight import (
    get_category_breakdown,
    get_merchant_leaderboard,
    get_spender_breakdown,
    get_spending_trend,
    get_summary,
)


async def _get_uncategorized_id(db, space_id):
    stmt = select(Category).where(
        Category.space_id == space_id, Category.is_system.is_(True)
    )
    result = await db.execute(stmt)
    return result.scalar_one().id


async def _create_test_expense(
    db, space_id, user_id, merchant, amount, cat_id, hours_ago=1
):
    """Helper to create a test expense."""
    data = ExpenseCreate(
        merchant=merchant,
        purchase_datetime=datetime.now(UTC) - timedelta(hours=hours_ago),
        amount=Decimal(str(amount)),
        category_id=cat_id,
        spender_id=user_id,
    )
    return await create_expense(db, space_id, data, user_id)


@pytest.mark.asyncio
async def test_summary_total(db_session, test_user, test_space):
    """Summary returns correct total for expenses in current window."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Store A", 50, cat_id
    )
    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Store B", 30, cat_id
    )

    result = await get_summary(db_session, test_space.id, period="this_month")
    assert result["total_spent"] == Decimal("80.00")


@pytest.mark.asyncio
async def test_summary_no_prior_data_delta_null(db_session, test_user, test_space):
    """Delta is null when there's no prior data."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Store", 100, cat_id
    )

    result = await get_summary(db_session, test_space.id, period="this_month")
    assert result["delta_pct"] is None


@pytest.mark.asyncio
async def test_category_breakdown(db_session, test_user, test_space):
    """Category breakdown groups by category correctly."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)

    # Create a second category
    from app.schemas.category import CategoryCreate
    from app.services.category import create_category

    groceries = await create_category(
        db_session, test_space.id, CategoryCreate(name="Groceries")
    )

    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Walmart", 60, groceries.id
    )
    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Amazon", 40, cat_id
    )

    result = await get_category_breakdown(
        db_session, test_space.id, period="this_month"
    )
    assert len(result) == 2

    totals = {r["category_name"]: r["total"] for r in result}
    assert totals["Groceries"] == Decimal("60.00")
    assert totals["Uncategorized"] == Decimal("40.00")


@pytest.mark.asyncio
async def test_merchant_leaderboard(db_session, test_user, test_space):
    """Merchant leaderboard ordered by amount DESC."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)

    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Walmart", 100, cat_id, hours_ago=1
    )
    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Target", 50, cat_id, hours_ago=2
    )
    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Walmart", 30, cat_id, hours_ago=3
    )

    result = await get_merchant_leaderboard(
        db_session, test_space.id, period="this_month"
    )
    assert len(result) == 2
    assert result[0]["merchant"] == "Walmart"  # higher total
    assert result[0]["total"] == Decimal("130.00")
    assert result[0]["count"] == 2
    assert result[1]["merchant"] == "Target"
    assert result[1]["total"] == Decimal("50.00")


@pytest.mark.asyncio
async def test_spender_breakdown(db_session, test_user, second_user, test_space):
    """Spender breakdown shows per-user totals."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)

    # Add second user as member
    from app.models import SpaceMember

    member = SpaceMember(space_id=test_space.id, user_id=second_user.id)
    db_session.add(member)
    await db_session.flush()

    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Store", 70, cat_id
    )
    await _create_test_expense(
        db_session, test_space.id, second_user.id, "Store", 30, cat_id
    )

    result = await get_spender_breakdown(db_session, test_space.id, period="this_month")
    assert len(result) == 2
    totals = {r["display_name"]: r["total"] for r in result}
    assert totals["Test User"] == Decimal("70.00")
    assert totals["Second User"] == Decimal("30.00")


@pytest.mark.asyncio
async def test_spending_trend_returns_series(db_session, test_user, test_space):
    """Spending trend returns current and average series."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    await _create_test_expense(
        db_session, test_space.id, test_user.id, "Store", 50, cat_id
    )

    result = await get_spending_trend(db_session, test_space.id, period="this_month")
    assert "current_series" in result
    assert "average_series" in result
    assert isinstance(result["current_series"], list)
    # Should have at least one point
    assert len(result["current_series"]) >= 1
