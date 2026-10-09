import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth.jwt import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Expense, ExpenseLine
from app.services.time_window import TimeWindowResolver
from tests.insights_support import seed_insights


@pytest.fixture(autouse=True)
def request_database(real_db):
    """Use real connections without reusing app pools across pytest event loops."""

    async def get_test_db():
        async with real_db.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = get_test_db
    yield
    app.dependency_overrides.pop(get_db)


async def assert_alignment(client, space_id, filters, expected):
    """Exercise real routers, SQL and response serialization for every surface."""
    prefix = f"/api/v1/spaces/{space_id}"
    responses = {}
    for endpoint in (
        "summary",
        "spending-trend",
        "category-breakdown",
        "merchant-leaderboard",
        "spender-breakdown",
    ):
        response = await client.get(f"{prefix}/insights/{endpoint}", params=filters)
        assert response.status_code == 200, response.text
        responses[endpoint] = response.json()
    response = await client.get(
        f"{prefix}/expenses", params={**filters, "status": "confirmed", "limit": "100"}
    )
    assert response.status_code == 200, response.text
    expenses = response.json()["data"]
    assert Decimal(responses["summary"]["total_spent"]) == expected
    assert Decimal(responses["spending-trend"]["current_series"][-1]["cumulative"]) == (
        expected
    )
    for endpoint in ("category-breakdown", "merchant-leaderboard", "spender-breakdown"):
        assert sum(Decimal(item["total"]) for item in responses[endpoint]) == expected
    assert sum(Decimal(expense["total_amount"]) for expense in expenses) == expected
    assert all(expense["status"] == "confirmed" for expense in expenses)
    assert all(expense["space_id"] == str(space_id) for expense in expenses)
    return responses, expenses


@pytest.mark.parametrize(
    ("dimension", "expected"),
    [
        (None, "160"),
        ("spender", "135"),
        ("category", "125"),
        ("merchant", "125"),
        ("tag", "125"),
        ("payment_method", "125"),
    ],
)
async def test_own_dimension_alignment(real_db, dimension, expected):
    data = await seed_insights(real_db)
    filters = {"period": "this_month"}
    if dimension:
        filters[dimension] = data.combined_filters[dimension]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data.owner.id)},
    ) as client:
        await assert_alignment(client, data.space.id, filters, Decimal(expected))


async def test_combined_filters_identity_baseline_and_status(real_db):
    data = await seed_insights(real_db)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data.owner.id)},
    ) as client:
        responses, expenses = await assert_alignment(
            client, data.space.id, data.combined_filters, Decimal("100")
        )
        assert {expense["id"] for expense in expenses} == data.matching_ids
        assert responses["summary"]["delta_pct"] == "400.0"
        assert Decimal(
            responses["spending-trend"]["average_series"][-1]["cumulative"]
        ) == Decimal("20")
        assert responses["spender-breakdown"][0]["spender_id"] == str(data.owner.id)
        assert len(responses["spender-breakdown"]) == 1
        await assert_alignment(
            client,
            data.space.id,
            {**data.combined_filters, "spender": str(data.membership_id)},
            Decimal("0"),
        )
        # Optional status does not change the general Transactions default.
        prefix = f"/api/v1/spaces/{data.space.id}/expenses"
        unfiltered = await client.get(prefix, params={"period": "this_month"})
        assert unfiltered.status_code == 200
        assert len(unfiltered.json()["data"]) == 5
        pending = await client.get(prefix, params={"status": "pending"})
        assert pending.status_code == 200
        assert len(pending.json()["data"]) == 1
        invalid = await client.get(prefix, params={"status": "invalid"})
        assert invalid.status_code == 422


@pytest.mark.parametrize(
    "dimension", ["spender", "category", "merchant", "tag", "payment_method"]
)
async def test_combined_filters_are_and_not_or(real_db, dimension):
    data = await seed_insights(real_db)
    mismatches = {
        "spender": str(data.partner.id),
        "category": str(data.other_category_id),
        "merchant": "Other Store",
        "tag": "travel",
        "payment_method": str(data.other_category_id),
    }
    expected = Decimal("25") if dimension == "spender" else Decimal("0")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data.owner.id)},
    ) as client:
        await assert_alignment(
            client,
            data.space.id,
            {**data.combined_filters, dimension: mismatches[dimension]},
            expected,
        )


async def test_category_selects_expenses_without_dropping_or_duplicating_split_lines(
    real_db,
):
    data = await seed_insights(real_db)
    async with real_db.sessions() as db:
        expense = await db.get(Expense, uuid.UUID(next(iter(data.matching_ids))))
        lines = (
            await db.scalars(
                select(ExpenseLine).where(ExpenseLine.expense_id == expense.id)
            )
        ).all()
        lines[0].amount = expense.total_amount - Decimal("10")
        db.add(
            ExpenseLine(
                expense_id=expense.id,
                amount=Decimal("10"),
                category_id=data.other_category_id,
                line_order=1,
            )
        )
        await db.commit()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data.owner.id)},
    ) as client:
        responses, _ = await assert_alignment(
            client, data.space.id, data.combined_filters, Decimal("100")
        )
        totals = {
            item["category_id"]: Decimal(item["total"])
            for item in responses["category-breakdown"]
        }
        assert totals == {
            str(data.category_id): Decimal("90"),
            str(data.other_category_id): Decimal("10"),
        }


async def test_local_month_boundary_and_literal_merchant_matching(real_db):
    data = await seed_insights(real_db)
    resolver = TimeWindowResolver(data.space.timezone)
    start, end = resolver.get_current_window("monthly")
    async with real_db.sessions() as db:
        expense = await db.get(Expense, uuid.UUID(next(iter(data.matching_ids))))
        literal_total = expense.total_amount
        expense.merchant = "Market_%"
        expense.merchant_normalized = "market_%"
        # Included at the space-local month start, even though it is not UTC midnight.
        expense.purchase_datetime = start
        await db.commit()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data.owner.id)},
    ) as client:
        responses, _ = await assert_alignment(
            client,
            data.space.id,
            {**data.combined_filters, "merchant": "_%"},
            literal_total,
        )
        assert datetime.fromisoformat(responses["summary"]["window_start"]) == start
        assert datetime.fromisoformat(responses["summary"]["window_end"]) == end
        async with real_db.sessions() as db:
            expense = await db.get(Expense, uuid.UUID(next(iter(data.matching_ids))))
            expense.purchase_datetime = start - timedelta(microseconds=1)
            await db.commit()
        await assert_alignment(
            client,
            data.space.id,
            {**data.combined_filters, "merchant": "_%"},
            Decimal("0"),
        )
