from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Category
from app.schemas.expense import ExpenseCreate
from app.services.expense import create_expense
from app.services.insight import (
    _average_series,
    _to_cumulative,
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


def test_to_cumulative_fills_gaps():
    """Cumulative series must include non-spending days with carried-forward values."""
    daily = {0: Decimal("100"), 2: Decimal("50"), 5: Decimal("30")}
    result = _to_cumulative(daily)

    # Must have entries for every day 0..5
    assert list(result.keys()) == [0, 1, 2, 3, 4, 5]

    # Day 0: 100, Day 1: still 100 (no spend), Day 2: 150, etc.
    assert result[0] == Decimal("100")
    assert result[1] == Decimal("100")
    assert result[2] == Decimal("150")
    assert result[3] == Decimal("150")
    assert result[4] == Decimal("150")
    assert result[5] == Decimal("180")


def test_to_cumulative_empty():
    """Empty input returns empty output."""
    assert _to_cumulative({}) == {}


def test_to_cumulative_single_day():
    """Single day input returns single entry."""
    result = _to_cumulative({3: Decimal("42")})
    assert list(result.keys()) == [0, 1, 2, 3]
    assert result[0] == Decimal("0")
    assert result[3] == Decimal("42")


def test_average_series_with_filled_cumulative():
    """Average series uses dense cumulative data from all periods."""
    series1 = _to_cumulative({0: Decimal("100"), 2: Decimal("50")})
    # series1 → {0: 100, 1: 100, 2: 150}
    series2 = _to_cumulative({0: Decimal("80"), 1: Decimal("40")})
    # series2 → {0: 80, 1: 120}
    series3 = _to_cumulative({0: Decimal("60"), 2: Decimal("90")})
    # series3 → {0: 60, 1: 60, 2: 150}

    avg = _average_series([series1, series2, series3])

    # All series have days 0 and 1; only series1 and series3 have day 2
    assert 0 in avg
    assert 1 in avg
    assert 2 in avg

    # Day 0: (100 + 80 + 60) / 3 = 80
    assert avg[0] == Decimal("80")
    # Day 1: (100 + 120 + 60) / 3
    assert avg[1] == (Decimal("100") + Decimal("120") + Decimal("60")) / 3
    # Day 2: (150 + 150) / 2 = 150  (series2 ends at day 1)
    assert avg[2] == Decimal("150")


def test_average_series_skips_empty_period():
    """When one prior period had zero expenses, _to_cumulative returns {}
    and _average_series averages over only the periods that had data."""
    series_with_data = _to_cumulative({0: Decimal("100"), 2: Decimal("50")})
    empty_period = _to_cumulative({})  # month with zero expenses → {}

    avg = _average_series([series_with_data, empty_period])

    # Empty dict contributes nothing — average is just the one series
    assert avg == series_with_data
