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
    assert result["timeframe"] == "monthly"
    assert isinstance(result["current_series"], list)
    # Should have at least one point
    assert len(result["current_series"]) >= 1


def test_to_cumulative_fills_gaps():
    """Cumulative series must include non-spending days with carried-forward values."""
    daily = {1: Decimal("100"), 3: Decimal("50"), 6: Decimal("30")}
    result = _to_cumulative(daily)

    # Must have entries for every day 1..6
    assert list(result.keys()) == [1, 2, 3, 4, 5, 6]

    # Day 1: 100, Day 2: still 100 (no spend), Day 3: 150, etc.
    assert result[1] == Decimal("100")
    assert result[2] == Decimal("100")
    assert result[3] == Decimal("150")
    assert result[4] == Decimal("150")
    assert result[5] == Decimal("150")
    assert result[6] == Decimal("180")


def test_to_cumulative_empty():
    """Empty input returns empty output."""
    assert _to_cumulative({}) == {}


def test_to_cumulative_single_day():
    """Single day input fills from 1 to max key."""
    result = _to_cumulative({3: Decimal("42")})
    assert list(result.keys()) == [1, 2, 3]
    assert result[1] == Decimal("0")
    assert result[2] == Decimal("0")
    assert result[3] == Decimal("42")


def test_average_series_with_filled_cumulative():
    """Average series divides by total series count, not per-day count."""
    series1 = _to_cumulative({1: Decimal("100"), 3: Decimal("50")}, period_days=3)
    # series1 → {1: 100, 2: 100, 3: 150}
    series2 = _to_cumulative({1: Decimal("80"), 2: Decimal("40")}, period_days=3)
    # series2 → {1: 80, 2: 120, 3: 120}
    series3 = _to_cumulative({1: Decimal("60"), 3: Decimal("90")}, period_days=3)
    # series3 → {1: 60, 2: 60, 3: 150}

    avg = _average_series([series1, series2, series3])

    assert len(avg) == 3

    # Day 1: (100 + 80 + 60) / 3 = 80
    assert avg[1] == Decimal("80")
    # Day 2: (100 + 120 + 60) / 3 ≈ 93.33
    assert avg[2] == (Decimal("100") + Decimal("120") + Decimal("60")) / 3
    # Day 3: (150 + 120 + 150) / 3 = 140
    assert avg[3] == (Decimal("150") + Decimal("120") + Decimal("150")) / 3


def test_average_series_includes_empty_period_as_zeros():
    """When one prior period had zero expenses but is extended via period_days,
    it contributes zeros to the average (lowering it), not being excluded."""
    series_with_data = _to_cumulative(
        {1: Decimal("100"), 3: Decimal("50")}, period_days=3
    )
    # → {1: 100, 2: 100, 3: 150}
    empty_period = _to_cumulative({}, period_days=3)
    # → {1: 0, 2: 0, 3: 0}

    avg = _average_series([series_with_data, empty_period])

    # Divides by 2 (total series), not just the one with data
    assert avg[1] == Decimal("50")  # (100 + 0) / 2
    assert avg[3] == Decimal("75")  # (150 + 0) / 2


def test_to_cumulative_extends_to_period_days():
    """With period_days, series extends beyond last expense day."""
    daily = {1: Decimal("100"), 3: Decimal("50")}
    result = _to_cumulative(daily, period_days=7)
    assert list(result.keys()) == [1, 2, 3, 4, 5, 6, 7]
    assert result[1] == Decimal("100")
    assert result[3] == Decimal("150")
    assert result[7] == Decimal("150")  # carried forward


def test_to_cumulative_empty_with_period_days():
    """Empty daily data with period_days returns all zeros."""
    result = _to_cumulative({}, period_days=5)
    assert list(result.keys()) == [1, 2, 3, 4, 5]
    assert all(v == Decimal("0") for v in result.values())


def test_average_series_normalized_never_decreases():
    """Average of cumulative series must never decrease, even when
    historical periods have different lengths (e.g., Feb 28 vs Mar 31).

    All series should be extended to the same period_days before averaging,
    and averaging should divide by total series count (not per-day count).
    """
    # Simulate 3 prior months all normalized to 31 days
    feb = _to_cumulative({1: Decimal("100"), 15: Decimal("200")}, period_days=31)
    mar = _to_cumulative({1: Decimal("80"), 20: Decimal("300")}, period_days=31)
    jan = _to_cumulative({1: Decimal("50"), 10: Decimal("150")}, period_days=31)

    avg = _average_series([feb, mar, jan])

    # All 3 series have 31 entries, so avg should have 31 entries
    assert len(avg) == 31

    # Cumulative average must never decrease
    prev = Decimal("0")
    for day in range(1, 32):
        assert avg[day] >= prev, f"Average decreased at day {day}: {avg[day]} < {prev}"
        prev = avg[day]


def test_average_series_divides_by_total_count():
    """_average_series must divide by total number of series, not by
    the number of series that contributed to each day.

    When all series are extended to the same period_days, this is
    inherently correct since every series has every day."""
    s1 = _to_cumulative({1: Decimal("90")}, period_days=3)
    # s1 → {1: 90, 2: 90, 3: 90}
    s2 = _to_cumulative({1: Decimal("60")}, period_days=3)
    # s2 → {1: 60, 2: 60, 3: 60}
    s3 = _to_cumulative({}, period_days=3)
    # s3 → {1: 0, 2: 0, 3: 0}

    avg = _average_series([s1, s2, s3])

    # Day 1: (90 + 60 + 0) / 3 = 50
    assert avg[1] == Decimal("50")
    assert avg[2] == Decimal("50")
    assert avg[3] == Decimal("50")
