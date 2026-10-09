from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.auth.jwt import create_access_token
from app.db.session import get_db
from app.main import app
from tests.weekly_multi_support import seed_weekly_multi


@pytest.mark.parametrize(
    "selected,count,total", [(1, 4, 20), (2, 8, 40), (3, 9, 60), (0, 0, 0)]
)
async def test_weekly_multi_all_surfaces_bounded_queries_dst(
    real_db, monkeypatch, selected, count, total
):
    # Week after DST begins has a 167-hour preceding completed window.
    now = datetime(2026, 3, 10, 12, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr("app.services.insight.datetime", Clock)
    data = await seed_weekly_multi(real_db, now)
    assert (data["windows"][0][1] - data["windows"][0][0]).total_seconds() < 168 * 3600

    async def test_db():
        async with real_db.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if (
            statement.lstrip().upper().startswith("SELECT")
            and "FROM expenses" in statement
        ):
            statements.append(statement)

    event.listen(real_db.engine.sync_engine, "before_cursor_execute", record)
    categories = data["categories"][:selected] if selected else data["categories"][3:]
    params = [
        ("period", "this_week"),
        ("spender", str(data["owner"].id)),
        *(("category", str(category.id)) for category in categories),
        ("merchant", "Weekly Match"),
        ("merchant", "No match"),
        ("tag", "#WEEKLY-RED"),
        ("tag", "weekly-blue"),
        ("payment_method", str(data["method"].id)),
    ]
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"access_token": create_access_token(data["owner"].id)},
        ) as client:
            base = f"/api/v1/spaces/{data['space'].id}"
            summary_response = await client.get(
                f"{base}/insights/summary", params=params
            )
            assert summary_response.status_code == 200, summary_response.text
            assert len(statements) == 2
            statements.clear()
            trend_response = await client.get(
                f"{base}/insights/spending-trend", params=params
            )
            assert trend_response.status_code == 200, trend_response.text
            assert len(statements) == 2
            summary, trend = summary_response.json(), trend_response.json()
            assert (
                summary["average_period_count"]
                == trend["average_period_count"]
                == count
            )
            assert Decimal(summary["total_spent"]) == total
            assert Decimal(trend["current_series"][-1]["cumulative"]) == total
            if count:
                assert Decimal(trend["average_series"][-1]["cumulative"]) == 100
                assert Decimal(summary["delta_pct"]) == total - 100
            else:
                assert trend["average_series"] == []
                assert summary["delta_pct"] is None
            for endpoint in (
                "category-breakdown",
                "merchant-leaderboard",
                "spender-breakdown",
            ):
                response = await client.get(
                    f"{base}/insights/{endpoint}", params=params
                )
                assert response.status_code == 200
                assert sum(Decimal(item["total"]) for item in response.json()) == total
            response = await client.get(
                f"{base}/expenses", params=[*params, ("status", "confirmed")]
            )
            assert response.status_code == 200
            assert (
                sum(Decimal(item["total_amount"]) for item in response.json()["data"])
                == total
            )
            # Last Week uses the actual DST-safe previous calendar window.
            last = await client.get(
                f"{base}/insights/summary",
                params=[
                    ("period", "last_week"),
                    ("spender", str(data["owner"].id)),
                    *(("category", str(category.id)) for category in categories),
                    ("merchant", "Weekly Match"),
                ],
            )
            assert last.status_code == 200
            assert (
                datetime.fromisoformat(last.json()["window_start"])
                == data["windows"][0][0]
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        event.remove(real_db.engine.sync_engine, "before_cursor_execute", record)
