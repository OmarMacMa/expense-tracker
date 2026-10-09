from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.services.time_window import TimeWindowResolver


@pytest.mark.parametrize("count", [0, 4, 8, 9])
async def test_weekly_average_api_metadata(
    auth_client, test_user_with_space, monkeypatch, count
):
    """API contracts expose actual filtered contributors for summary and trend."""
    now = datetime(2026, 3, 10, 12, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr("app.services.insight.datetime", Clock)
    data = test_user_with_space
    base = f"/api/v1/spaces/{data['space'].id}"
    windows = TimeWindowResolver("UTC").get_previous_windows(
        "weekly", count=10, ref_date=now
    )
    included = list(range(count - 1)) + [8] if count else []
    for when, merchant, amount in [
        (now, "Matching", "50"),
        *((windows[i][0], "Matching", "100") for i in included),
        (windows[9][0], "Matching", "9000"),
        (windows[4][0] + timedelta(hours=1), "Other", "5000"),
    ]:
        response = await auth_client.post(
            f"{base}/expenses",
            json={
                "merchant": merchant,
                "purchase_datetime": when.isoformat(),
                "amount": amount,
                "category_id": str(data["category_id"]),
                "spender_id": str(data["user"].id),
            },
        )
        assert response.status_code == 201, response.text

    params = {"period": "this_week", "merchant": "Matching"}
    summary_response = await auth_client.get(f"{base}/insights/summary", params=params)
    trend_response = await auth_client.get(
        f"{base}/insights/spending-trend", params=params
    )
    assert summary_response.status_code == trend_response.status_code == 200
    summary, trend = summary_response.json(), trend_response.json()
    assert summary["average_period_count"] == trend["average_period_count"] == count
    assert Decimal(summary["total_spent"]) == Decimal("50")
    if count:
        assert Decimal(summary["delta_pct"]) == Decimal("-50.0")
        assert len(trend["average_series"]) == 7
        assert all(
            Decimal(point["cumulative"]) == 100 for point in trend["average_series"]
        )
    else:
        assert summary["delta_pct"] is None
        assert trend["average_series"] == []

    last_week = await auth_client.get(
        f"{base}/insights/spending-trend", params={"period": "last_week"}
    )
    assert last_week.status_code == 200
    assert last_week.json()["current_day"] is None
    yearly = await auth_client.get(
        f"{base}/insights/spending-trend", params={"period": "ytd"}
    )
    assert yearly.status_code == 200
    assert yearly.json()["average_series"] == []
    assert yearly.json()["average_period_count"] == 0
