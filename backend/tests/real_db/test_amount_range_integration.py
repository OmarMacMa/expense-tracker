from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

from app.auth.jwt import create_access_token
from app.db.session import get_db
from app.main import app
from tests.amount_range_support import weekly_range_dataset


@pytest.mark.parametrize("period", ["this_week", "last_week"])
@pytest.mark.parametrize(
    "maximum,count", [("", 9), ("299.99", 8), ("199.99", 4), ("99.99", 0)]
)
async def test_integrated_range_weekly_filters_dst_bounded_history(
    real_db, monkeypatch, period, maximum, count
):
    now = datetime(2026, 3, 10, 12, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr("app.services.insight.datetime", Clock)
    data = await weekly_range_dataset(real_db, now)
    assert (data["windows"][0][1] - data["windows"][0][0]).total_seconds() < 168 * 3600

    async def sessions():
        async with real_db.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = sessions
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if (
            statement.lstrip().upper().startswith("SELECT")
            and "FROM expenses" in statement
        ):
            statements.append(statement)

    event.listen(real_db.engine.sync_engine, "before_cursor_execute", record)
    params = [
        ("period", period),
        ("spender", str(data["owner"].id)),
        *(("category", str(category.id)) for category in data["categories"][:3]),
        ("merchant", "Weekly Match"),
        ("merchant", "No match"),
        ("tag", "weekly-red"),
        ("tag", "#WEEKLY-BLUE"),
        ("payment_method", str(data["method"].id)),
        ("min_amount", "0"),
        ("max_amount", maximum),
    ]
    # Last Week shifts the bounded history by one week, admitting only the tenth
    # week (50) and excluding the former first week (100).
    expected_count = count if period == "this_week" else count if count else 1
    expected_total = (
        Decimal("540")
        if period == "this_week"
        else Decimal("100") if not maximum or Decimal(maximum) >= 100 else Decimal("0")
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            cookies={"access_token": create_access_token(data["owner"].id)},
        ) as client:
            base = f"/api/v1/spaces/{data['space'].id}"
            summary = await client.get(f"{base}/insights/summary", params=params)
            assert summary.status_code == 200, summary.text
            assert len(statements) == 2
            statements.clear()
            trend = await client.get(f"{base}/insights/spending-trend", params=params)
            assert trend.status_code == 200, trend.text
            assert len(statements) == 2
            summary, trend = summary.json(), trend.json()
            assert (
                summary["average_period_count"]
                == trend["average_period_count"]
                == expected_count
            )
            assert Decimal(summary["total_spent"]) == expected_total
            assert Decimal(trend["current_series"][-1]["cumulative"]) == expected_total
            if not expected_count:
                assert summary["delta_pct"] is None
                assert trend["average_series"] == []
            else:
                history_total = (
                    Decimal("1500")
                    if count == 9
                    else (
                        Decimal("1200")
                        if count == 8
                        else Decimal("400") if count == 4 else Decimal("0")
                    )
                )
                if period == "last_week":
                    history_total += Decimal("-50") if count else Decimal("50")
                expected_average = history_total / expected_count
                assert abs(
                    Decimal(trend["average_series"][-1]["cumulative"])
                    - expected_average
                ) < Decimal("0.000000000000000000001")
            for endpoint in (
                "category-breakdown",
                "merchant-leaderboard",
                "spender-breakdown",
            ):
                response = await client.get(
                    f"{base}/insights/{endpoint}", params=params
                )
                assert response.status_code == 200, response.text
                assert (
                    sum(Decimal(item["total"]) for item in response.json())
                    == expected_total
                )
            cursor, rows = None, []
            while True:
                response = await client.get(
                    f"{base}/expenses",
                    params=[
                        *params,
                        ("status", "confirmed"),
                        ("limit", "2"),
                        *([("cursor", cursor)] if cursor else []),
                    ],
                )
                assert response.status_code == 200, response.text
                page = response.json()
                rows.extend(page["data"])
                cursor = page["next_cursor"]
                if not cursor:
                    break
            assert len({row["id"] for row in rows}) == len(rows)
            assert sum(Decimal(row["total_amount"]) for row in rows) == expected_total
            if period == "last_week":
                assert (
                    datetime.fromisoformat(summary["window_start"])
                    == data["windows"][0][0]
                )
    finally:
        app.dependency_overrides.pop(get_db, None)
        event.remove(real_db.engine.sync_engine, "before_cursor_execute", record)
