from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth.jwt import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Expense, Limit
from tests.amount_range_support import range_dataset

ENDPOINTS = [
    "expenses",
    "insights/summary",
    "insights/spending-trend",
    "insights/category-breakdown",
    "insights/merchant-leaderboard",
    "insights/spender-breakdown",
]


@pytest_asyncio.fixture(autouse=True)
async def isolated_api_sessions(real_db):
    async def sessions():
        async with real_db.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = sessions
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_range_agreement_history_pagination_and_tenancy(real_db):
    data = await range_dataset(real_db)
    base = f"/api/v1/spaces/{data['space'].id}"
    filters = {**data["filters"], "min_amount": "10.10", "max_amount": "20.20"}
    async with real_db.sessions() as db:
        db.add(
            Limit(
                space_id=data["space"].id,
                name="Unfiltered budget",
                timeframe="monthly",
                threshold_amount=Decimal("500"),
            )
        )
        await db.commit()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data["owner"].id)},
    ) as client:
        limits_before = (await client.get(f"{base}/insights/limit-progress")).json()
        assert Decimal(limits_before[0]["spent"]) == Decimal("1090.31")
        summary = (await client.get(f"{base}/insights/summary", params=filters)).json()
        assert Decimal(summary["total_spent"]) == Decimal("30.30")
        assert Decimal(summary["delta_pct"]) == Decimal("200")
        trend = (
            await client.get(f"{base}/insights/spending-trend", params=filters)
        ).json()
        assert Decimal(trend["current_series"][-1]["cumulative"]) == Decimal("30.30")
        assert Decimal(trend["average_series"][-1]["cumulative"]) == Decimal("10.10")
        for endpoint in (
            "category-breakdown",
            "merchant-leaderboard",
            "spender-breakdown",
        ):
            response = await client.get(f"{base}/insights/{endpoint}", params=filters)
            assert response.status_code == 200, response.text
            assert sum(Decimal(row["total"]) for row in response.json()) == Decimal(
                "30.30"
            )
        cursor = None
        matching = []
        while True:
            params = {**filters, "limit": "1"}
            if cursor:
                params["cursor"] = cursor
            response = await client.get(f"{base}/expenses", params=params)
            assert response.status_code == 200, response.text
            page = response.json()
            matching.extend(page["data"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert {row["id"] for row in matching} == {
            str(data["ids"]["Range Small"]),
            str(data["ids"]["Range Medium"]),
        }
        assert len(matching) == 2
        assert sum(Decimal(row["total_amount"]) for row in matching) == Decimal("30.30")
        # A chart's own dimension must not silently ignore its filter.
        merchant_filtered = {**filters, "merchant": "Range Small"}
        for endpoint in ENDPOINTS:
            response = await client.get(f"{base}/{endpoint}", params=merchant_filtered)
            assert response.status_code == 200, response.text
            value = response.json()
            if endpoint == "expenses":
                assert [row["id"] for row in value["data"]] == [
                    str(data["ids"]["Range Small"])
                ]
            elif endpoint == "insights/summary":
                assert Decimal(value["total_spent"]) == Decimal("10.10")
            elif endpoint == "insights/spending-trend":
                assert Decimal(value["current_series"][-1]["cumulative"]) == Decimal(
                    "10.10"
                )
            else:
                assert sum(Decimal(row["total"]) for row in value) == Decimal("10.10")
        cleared = (
            await client.get(f"{base}/insights/summary", params=data["filters"])
        ).json()
        assert Decimal(cleared["total_spent"]) == Decimal("1030.30")
        limits_after = (await client.get(f"{base}/insights/limit-progress")).json()
        assert limits_after == limits_before
        for endpoint in ENDPOINTS:
            denied = await client.get(
                f"/api/v1/spaces/{data['foreign'].id}/{endpoint}", params=filters
            )
            assert denied.status_code == 403
    async with real_db.sessions() as db:
        assert (
            await db.scalar(
                select(Expense.total_amount).where(
                    Expense.space_id == data["space"].id,
                    Expense.id == data["ids"]["Range Outlier"],
                )
            )
        ) == Decimal("1000")


@pytest.mark.parametrize(
    "bounds,total",
    [
        ({"min_amount": "20.20"}, "1020.20"),
        ({"max_amount": "10.10"}, "10.10"),
        ({"min_amount": "20.20", "max_amount": "20.20"}, "20.20"),
        ({"min_amount": "0", "max_amount": "0"}, "0"),
        ({"min_amount": "", "max_amount": ""}, "1030.30"),
        (
            {
                "min_amount": "10.100000000000000001",
                "max_amount": "20.199999999999999999",
            },
            "0",
        ),
        ({"min_amount": "999999999999999999999999999999"}, "0"),
    ],
)
async def test_valid_boundaries_on_all_surfaces(real_db, bounds, total):
    data = await range_dataset(real_db)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data["owner"].id)},
    ) as client:
        for endpoint in ENDPOINTS:
            response = await client.get(
                f"/api/v1/spaces/{data['space'].id}/{endpoint}",
                params={**data["filters"], **bounds},
            )
            assert response.status_code == 200, response.text
            value = response.json()
            if endpoint == "expenses":
                actual = sum(Decimal(row["total_amount"]) for row in value["data"])
            elif endpoint == "insights/summary":
                actual = Decimal(value["total_spent"])
            elif endpoint == "insights/spending-trend":
                actual = Decimal(value["current_series"][-1]["cumulative"])
            else:
                actual = sum(Decimal(row["total"]) for row in value)
            assert actual == Decimal(total), (endpoint, value)


@pytest.mark.parametrize(
    "bounds",
    [
        {"min_amount": "-0.01"},
        {"max_amount": "-1"},
        {"min_amount": "NaN"},
        {"max_amount": "Infinity"},
        {"min_amount": "-Infinity"},
        {"min_amount": "nope"},
        {"max_amount": "1.2.3"},
        {"min_amount": "2", "max_amount": "1"},
    ],
)
async def test_invalid_range_is_422_everywhere(real_db, bounds):
    owner = await real_db.user()
    space = await real_db.space(owner)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(owner.id)},
    ) as client:
        for endpoint in ENDPOINTS:
            response = await client.get(
                f"/api/v1/spaces/{space.id}/{endpoint}", params=bounds
            )
            assert response.status_code == 422, (endpoint, response.text)
            assert response.json()["error"]["code"] == "VALIDATION_ERROR"
