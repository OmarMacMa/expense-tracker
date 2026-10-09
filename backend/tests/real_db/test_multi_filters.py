from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token
from app.db.session import get_db
from app.main import app
from tests.filter_support import filter_dataset

ENDPOINTS = [
    "insights/summary",
    "insights/spending-trend",
    "insights/category-breakdown",
    "insights/merchant-leaderboard",
    "insights/spender-breakdown",
    "expenses",
]


@pytest_asyncio.fixture(autouse=True)
async def api_database(real_db):
    """Each test owns its pool/event loop, including authentication reads."""

    async def get_test_db():
        async with real_db.sessions() as session:
            yield session

    app.dependency_overrides[get_db] = get_test_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_repeated_mixed_filters_all_surfaces_and_pagination(real_db):
    data = await filter_dataset(real_db)
    base = f"/api/v1/spaces/{data['space'].id}"
    params = [
        ("period", "this_month"),
        ("spender", str(data["actor"].id)),
        *(("category", str(category.id)) for category in data["categories"]),
        ("category", str(data["categories"][0].id)),
        ("tag", "#RED"),
        ("tag", " blue "),
        ("tag", "red"),
        ("merchant", "Cafe, North"),
        ("merchant", "Shop %"),
        *(("payment_method", str(method.id)) for method in data["methods"]),
    ]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data["actor"].id)},
    ) as client:
        summary = (await client.get(f"{base}/insights/summary", params=params)).json()
        assert Decimal(summary["total_spent"]) == 240
        assert Decimal(summary["delta_pct"]) == 2300  # monthly baseline remains /3
        trend = (
            await client.get(f"{base}/insights/spending-trend", params=params)
        ).json()
        assert Decimal(trend["current_series"][-1]["cumulative"]) == 240
        assert Decimal(trend["average_series"][-1]["cumulative"]) == 10
        categories = (
            await client.get(f"{base}/insights/category-breakdown", params=params)
        ).json()
        assert {item["category_id"] for item in categories} == {
            str(category.id) for category in data["categories"]
        }
        assert sum(Decimal(item["total"]) for item in categories) == 240
        merchants = (
            await client.get(f"{base}/insights/merchant-leaderboard", params=params)
        ).json()
        assert sum(item["count"] for item in merchants) == 24
        assert sum(Decimal(item["total"]) for item in merchants) == 240
        spenders = (
            await client.get(f"{base}/insights/spender-breakdown", params=params)
        ).json()
        assert len(spenders) == 1 and spenders[0]["spender_id"] == str(data["actor"].id)
        assert Decimal(spenders[0]["total"]) == 240
        first = (
            await client.get(
                f"{base}/expenses", params=[*params, ("status", "confirmed")]
            )
        ).json()
        second = (
            await client.get(
                f"{base}/expenses",
                params=[
                    *params,
                    ("status", "confirmed"),
                    ("cursor", first["next_cursor"]),
                ],
            )
        ).json()
        expenses = [*first["data"], *second["data"]]
        assert len(expenses) == len({item["id"] for item in expenses}) == 24
        assert second["next_cursor"] is None
        # Clearing category retains spender and tag dimensions.
        cleared = [
            (key, value) for key, value in params if key not in ("category", "merchant")
        ]
        response = await client.get(f"{base}/insights/summary", params=cleared)
        assert Decimal(response.json()["total_spent"]) == 240
        # Single existing query values and duplicate selection agree.
        single = [("period", "this_month"), ("category", str(data["categories"][0].id))]
        response = await client.get(f"{base}/insights/summary", params=single)
        assert Decimal(response.json()["total_spent"]) == 170
        duplicate = await client.get(
            f"{base}/insights/summary", params=[*single, single[-1]]
        )
        assert duplicate.json() == response.json()
        # Every dimension accumulates: two spenders include both, not just the last.
        both = [
            ("period", "this_month"),
            ("spender", str(data["actor"].id)),
            ("spender", str(data["partner"].id)),
        ]
        assert (
            Decimal(
                (await client.get(f"{base}/insights/summary", params=both)).json()[
                    "total_spent"
                ]
            )
            == 330
        )
        # General transactions still include pending; Insights context excludes them.
        general = await client.get(
            f"{base}/expenses",
            params=[("period", "this_month"), ("merchant", "Pending Only")],
        )
        assert len(general.json()["data"]) == 1
        confirmed = await client.get(
            f"{base}/expenses",
            params=[
                ("period", "this_month"),
                ("merchant", "Pending Only"),
                ("status", "confirmed"),
            ],
        )
        assert confirmed.json()["data"] == []


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_invalid_uuid_and_cross_space_filters_are_safe(real_db, endpoint):
    data = await filter_dataset(real_db)
    url = f"/api/v1/spaces/{data['space'].id}/{endpoint}"
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": create_access_token(data["actor"].id)},
    ) as client:
        for dimension in ("category", "spender", "payment_method"):
            response = await client.get(
                url, params=[(dimension, str(data["actor"].id)), (dimension, "invalid")]
            )
            assert response.status_code == 422
        for dimension, value in (
            ("category", data["other_category"].id),
            ("spender", data["outsider"].id),
            ("payment_method", data["other_method"].id),
        ):
            response = await client.get(
                url, params=[("period", "this_month"), (dimension, str(value))]
            )
            assert response.status_code == 200
            result = response.json()
            if endpoint == "insights/summary":
                assert Decimal(result["total_spent"]) == 0
            elif endpoint == "insights/spending-trend":
                assert all(
                    Decimal(point["cumulative"]) == 0
                    for point in result["current_series"]
                )
            elif endpoint == "expenses":
                assert result["data"] == []
            else:
                assert result == []
