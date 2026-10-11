from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from app.models import Category, Expense
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
from app.services.time_window import TimeWindowResolver


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
@pytest.mark.parametrize("period", ["this_week", "last_week"])
@pytest.mark.parametrize("older_week", range(4, 10))
async def test_weekly_baseline_includes_older_weeks(
    db_session, test_user, test_space, monkeypatch, period, older_week
):
    """Weeks 4–9 count, zero weeks and the selected/tenth weeks are excluded."""
    test_space.timezone = "America/New_York"
    ref = datetime(2026, 3, 9, 4, tzinfo=UTC)
    if period == "last_week":
        ref -= timedelta(weeks=1)
    monkeypatch.setattr("app.services.insight._resolve_ref_date", lambda *args: ref)
    resolver = TimeWindowResolver(test_space.timezone)
    start, end = resolver.get_current_window("weekly", ref)
    windows = resolver.get_previous_windows("weekly", count=10, ref_date=ref)
    cat_id = await _get_uncategorized_id(db_session, test_space.id)

    for purchase_datetime, amount in (
        (start, "50.00"),
        (windows[older_week - 1][0], "900.00"),
        (windows[9][0], "9000.00"),
        (end + timedelta(microseconds=1), "9000.00"),
    ):
        await create_expense(
            db_session,
            test_space.id,
            ExpenseCreate(
                merchant="Monthly bill",
                purchase_datetime=purchase_datetime,
                amount=Decimal(amount),
                category_id=cat_id,
                spender_id=test_user.id,
            ),
            test_user.id,
        )

    summary = await get_summary(db_session, test_space.id, period=period)
    trend = await get_spending_trend(db_session, test_space.id, period=period)

    assert summary["total_spent"] == Decimal("50.00")
    assert summary["delta_pct"] == Decimal("-94.4")
    assert summary["average_period_count"] == trend["average_period_count"] == 1
    assert len(trend["average_series"]) == 7
    assert all(
        point["cumulative"] == Decimal("900.00") for point in trend["average_series"]
    )
    assert trend["current_series"][-1]["cumulative"] == Decimal("50.00")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ref", "expected_start"),
    [
        (
            datetime(2026, 3, 9, 3, 59, 59, tzinfo=UTC),
            datetime(2026, 3, 2, 5, tzinfo=UTC),
        ),
        (
            datetime(2026, 3, 9, 4, tzinfo=UTC),
            datetime(2026, 3, 9, 4, tzinfo=UTC),
        ),
    ],
)
async def test_weekly_empty_baseline_at_local_monday_boundary(
    db_session, test_space, monkeypatch, ref, expected_start
):
    """The nine completed weeks follow local Monday boundaries across DST."""
    test_space.timezone = "America/New_York"
    monkeypatch.setattr("app.services.insight._resolve_ref_date", lambda *args: ref)
    resolver = TimeWindowResolver(test_space.timezone)
    windows = resolver.get_previous_windows("weekly", count=9, ref_date=ref)
    assert len(windows) == 9
    assert windows[0][1] + timedelta(microseconds=1) == expected_start
    for index, (start, end) in enumerate(windows):
        assert resolver.localize_for_display(start).weekday() == 0
        assert resolver.localize_for_display(end).weekday() == 6
        if index:
            assert end + timedelta(microseconds=1) == windows[index - 1][0]

    summary = await get_summary(db_session, test_space.id, period="this_week")
    trend = await get_spending_trend(db_session, test_space.id, period="this_week")
    assert summary["window_start"] == expected_start
    assert summary["total_spent"] == Decimal("0")
    assert summary["delta_pct"] is None
    assert trend["average_series"] == []
    assert summary["average_period_count"] == trend["average_period_count"] == 0


@pytest.mark.asyncio
async def test_monthly_baseline_remains_three_periods(
    db_session, test_user, test_space
):
    """Summary and trend retain three months, including empty months as zeros."""
    resolver = TimeWindowResolver(test_space.timezone)
    ref = datetime(2026, 3, 15, tzinfo=UTC)
    start, _ = resolver.get_current_window("monthly", ref)
    windows = resolver.get_previous_windows("monthly", count=4, ref_date=ref)
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    for purchase_datetime, amount in (
        (start, "50.00"),
        (windows[2][0], "300.00"),
        (windows[3][0], "9000.00"),
    ):
        await create_expense(
            db_session,
            test_space.id,
            ExpenseCreate(
                merchant="Store",
                purchase_datetime=purchase_datetime,
                amount=Decimal(amount),
                category_id=cat_id,
                spender_id=test_user.id,
            ),
            test_user.id,
        )
    summary = await get_summary(db_session, test_space.id, month="2026-03")
    trend = await get_spending_trend(db_session, test_space.id, month="2026-03")
    assert summary["total_spent"] == Decimal("50.00")
    assert summary["delta_pct"] == Decimal("-50.0")
    assert summary["average_period_count"] == trend["average_period_count"] == 3
    assert len(trend["average_series"]) == 31
    assert all(
        point["cumulative"] == Decimal("100.00") for point in trend["average_series"]
    )


def _freeze_insight_clock(monkeypatch, now):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr("app.services.insight.datetime", Clock)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [4, 8, 9])
async def test_weekly_actual_contributors_and_constant_queries(
    db_session, test_user, test_space, monkeypatch, count
):
    """The same nonzero weeks drive summary/trend in two expense SELECTs each."""
    now = datetime(2026, 3, 10, 12, tzinfo=UTC)
    _freeze_insight_clock(monkeypatch, now)
    resolver = TimeWindowResolver(test_space.timezone)
    windows = resolver.get_previous_windows("weekly", count=10, ref_date=now)
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    # Include week nine even with short history; never reach out to week ten.
    included = list(range(count - 1)) + [8]
    for index in included + [9]:
        await create_expense(
            db_session,
            test_space.id,
            ExpenseCreate(
                merchant="Bill",
                purchase_datetime=windows[index][0] + timedelta(days=2),
                amount=Decimal("900") if index == 8 else Decimal("100"),
                category_id=cat_id,
                spender_id=test_user.id,
            ),
            test_user.id,
        )
    queries = []

    def record_query(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and (
            "FROM expenses" in statement
        ):
            queries.append(statement)

    engine = db_session.bind.engine.sync_engine
    event.listen(engine, "before_cursor_execute", record_query)
    try:
        summary = await get_summary(db_session, test_space.id, period="this_week")
        assert len(queries) == 2
        queries.clear()
        trend = await get_spending_trend(db_session, test_space.id, period="this_week")
        assert len(queries) == 2
    finally:
        event.remove(engine, "before_cursor_execute", record_query)

    expected = (Decimal("100") * (count - 1) + Decimal("900")) / count
    assert summary["average_period_count"] == trend["average_period_count"] == count
    assert summary["delta_pct"] == Decimal("-100.0")
    assert [p["cumulative"] for p in trend["average_series"]] == [
        Decimal("0"),
        Decimal("0"),
        expected,
        expected,
        expected,
        expected,
        expected,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("now", "expected_start", "expected_end"),
    [
        (
            datetime(2026, 3, 9, 3, 30, tzinfo=UTC),
            datetime(2026, 2, 23, 5, tzinfo=UTC),
            datetime(2026, 3, 2, 5, tzinfo=UTC),
        ),
        (
            datetime(2026, 3, 9, 4, 30, tzinfo=UTC),
            datetime(2026, 3, 2, 5, tzinfo=UTC),
            datetime(2026, 3, 9, 4, tzinfo=UTC),
        ),
        (
            datetime(2026, 11, 2, 4, 30, tzinfo=UTC),
            datetime(2026, 10, 19, 4, tzinfo=UTC),
            datetime(2026, 10, 26, 4, tzinfo=UTC),
        ),
        (
            datetime(2026, 11, 2, 5, 30, tzinfo=UTC),
            datetime(2026, 10, 26, 4, tzinfo=UTC),
            datetime(2026, 11, 2, 5, tzinfo=UTC),
        ),
    ],
)
async def test_last_week_real_reference_resolver_across_dst(
    db_session, test_user, test_space, monkeypatch, now, expected_start, expected_end
):
    """Freeze the clock, not reference selection; also exercise expense listing."""
    from app.services.expense import list_expenses

    test_space.timezone = "America/New_York"
    _freeze_insight_clock(monkeypatch, now)
    # Direct inserts allow testing the autumn clock independently of wall time.
    selected = Expense(
        space_id=test_space.id,
        merchant="Selected",
        merchant_normalized="selected",
        purchase_datetime=expected_start,
        total_amount=Decimal("50"),
        spender_id=test_user.id,
        status="confirmed",
    )
    older = Expense(
        space_id=test_space.id,
        merchant="Older",
        merchant_normalized="older",
        purchase_datetime=expected_start - timedelta(hours=1),
        total_amount=Decimal("100"),
        spender_id=test_user.id,
        status="confirmed",
    )
    db_session.add_all([selected, older])
    await db_session.flush()
    summary = await get_summary(db_session, test_space.id, period="last_week")
    trend = await get_spending_trend(db_session, test_space.id, period="last_week")
    expenses = await list_expenses(db_session, test_space.id, period="last_week")
    assert summary["window_start"] == expected_start
    assert summary["window_end"] == expected_end - timedelta(microseconds=1)
    assert summary["total_spent"] == Decimal("50")
    assert summary["delta_pct"] == Decimal("-50.0")
    assert summary["average_period_count"] == trend["average_period_count"] == 1
    assert trend["current_day"] is None
    assert trend["average_series"][-1]["cumulative"] == Decimal("100")
    assert [row["id"] for row in expenses["data"]] == [selected.id]


@pytest.mark.asyncio
async def test_weekly_zero_pending_and_future_expenses_are_not_history(
    db_session, test_user, test_space, monkeypatch
):
    now = datetime(2026, 3, 10, 12, tzinfo=UTC)
    _freeze_insight_clock(monkeypatch, now)
    for when, amount, status in [
        (now - timedelta(weeks=2), "500", "pending"),
        (now + timedelta(hours=1), "900", "confirmed"),
    ]:
        db_session.add(
            Expense(
                space_id=test_space.id,
                merchant="Excluded",
                merchant_normalized="excluded",
                purchase_datetime=when,
                total_amount=Decimal(amount),
                spender_id=test_user.id,
                status=status,
            )
        )
    await db_session.flush()
    summary = await get_summary(db_session, test_space.id, period="this_week")
    trend = await get_spending_trend(db_session, test_space.id, period="this_week")
    assert summary["total_spent"] == 0
    assert summary["delta_pct"] is None
    assert summary["average_period_count"] == trend["average_period_count"] == 0
    assert trend["average_series"] == []
    assert all(point["cumulative"] == 0 for point in trend["current_series"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filter_name", ["spender_id", "category_id", "merchant", "tag", "payment_method_id"]
)
async def test_weekly_history_uses_active_filters(
    db_session, test_user, second_user, test_space, monkeypatch, filter_name
):
    from app.models import PaymentMethod, SpaceMember
    from app.schemas.category import CategoryCreate
    from app.services.category import create_category

    now = datetime(2026, 3, 10, 12, tzinfo=UTC)
    _freeze_insight_clock(monkeypatch, now)
    category = await create_category(
        db_session, test_space.id, CategoryCreate(name="Matching")
    )
    other_category = await _get_uncategorized_id(db_session, test_space.id)
    db_session.add(SpaceMember(space_id=test_space.id, user_id=second_user.id))
    method = PaymentMethod(
        space_id=test_space.id, owner_id=test_user.id, label="Matching"
    )
    db_session.add(method)
    await db_session.flush()
    for weeks, matching in [(0, True), (1, True), (2, False), (3, True)]:
        await create_expense(
            db_session,
            test_space.id,
            ExpenseCreate(
                merchant="Matching" if matching else "Other",
                purchase_datetime=now - timedelta(weeks=weeks),
                amount=Decimal("50") if weeks == 0 else Decimal("100"),
                category_id=category.id if matching else other_category,
                spender_id=test_user.id if matching else second_user.id,
                payment_method_id=method.id if matching else None,
                tags=["matching"] if matching else [],
            ),
            test_user.id,
        )
    value = {
        "spender_id": test_user.id,
        "category_id": category.id,
        "merchant": "MATCH",
        "tag": "#MATCHING",
        "payment_method_id": method.id,
    }[filter_name]
    summary = await get_summary(
        db_session, test_space.id, period="this_week", **{filter_name: value}
    )
    trend = await get_spending_trend(
        db_session, test_space.id, period="this_week", **{filter_name: value}
    )
    assert summary["average_period_count"] == trend["average_period_count"] == 2
    assert summary["total_spent"] == Decimal("50")
    assert summary["delta_pct"] == Decimal("-50.0")
    assert trend["average_series"][-1]["cumulative"] == Decimal("100")


@pytest.mark.asyncio
async def test_yearly_summary_retains_three_year_average(
    db_session, test_user, test_space, monkeypatch
):
    _freeze_insight_clock(monkeypatch, datetime(2026, 3, 10, 12, tzinfo=UTC))
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    for year, amount in [(2026, "50"), (2023, "300"), (2022, "9000")]:
        await create_expense(
            db_session,
            test_space.id,
            ExpenseCreate(
                merchant="Yearly",
                purchase_datetime=datetime(year, 1, 1, tzinfo=UTC),
                amount=Decimal(amount),
                category_id=cat_id,
                spender_id=test_user.id,
            ),
            test_user.id,
        )
    summary = await get_summary(db_session, test_space.id, period="ytd")
    trend = await get_spending_trend(db_session, test_space.id, period="ytd")
    assert summary["total_spent"] == Decimal("50")
    assert summary["delta_pct"] == Decimal("-50.0")
    assert summary["average_period_count"] == 3
    assert trend["average_period_count"] == 0
    assert trend["average_series"] == []


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
    assert result["current_day"] is not None
    assert 1 <= result["current_day"] <= len(result["current_series"])
    assert isinstance(result["current_series"], list)
    # Should have at least one point
    assert len(result["current_series"]) >= 1
    # Year reflects the space-tz year of the current window
    assert isinstance(result["year"], int)
    assert result["year"] >= 2020


@pytest.mark.asyncio
async def test_spending_trend_yearly_skips_average(db_session, test_user, test_space):
    """YTD trend returns current series but no average (too expensive)."""
    result = await get_spending_trend(db_session, test_space.id, period="ytd")
    assert result["timeframe"] == "yearly"
    assert result["average_series"] == []
    assert isinstance(result["current_series"], list)
    # YTD year matches the space-tz year of today
    assert result["year"] == datetime.now(UTC).year
    # YTD always contains "now" — current_day is set
    assert result["current_day"] is not None


@pytest.mark.asyncio
async def test_spending_trend_past_month_has_no_current_day(
    db_session, test_user, test_space
):
    """Past monthly periods should not expose a current day marker."""
    result = await get_spending_trend(db_session, test_space.id, period="last_month")
    assert result["current_day"] is None


@pytest.mark.asyncio
async def test_spending_trend_past_week_has_no_current_day(
    db_session, test_user, test_space
):
    """Past weekly periods should not expose a current day marker."""
    result = await get_spending_trend(db_session, test_space.id, period="last_week")
    assert result["current_day"] is None


@pytest.mark.asyncio
async def test_spending_trend_future_month_has_no_current_day(
    db_session, test_user, test_space
):
    """Future month-picker selections should not expose a current day marker."""
    now = datetime.now(UTC)
    future_year = now.year + 1
    result = await get_spending_trend(
        db_session, test_space.id, month=f"{future_year}-06"
    )
    assert result["current_day"] is None


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


def test_average_series_carries_forward_for_short_series():
    """If a series is shorter than others, its last cumulative value
    is carried forward so the average never decreases."""
    long_series = {1: Decimal("100"), 2: Decimal("200"), 3: Decimal("300")}
    short_series = {1: Decimal("50"), 2: Decimal("80")}
    # short_series missing day 3 — should carry forward 80

    avg = _average_series([long_series, short_series])

    # Day 3: (300 + 80) / 2 = 190 (not 300/1 = 300 or 300/2 = 150)
    assert avg[3] == Decimal("190")
    # Must never decrease
    assert avg[1] <= avg[2] <= avg[3]
