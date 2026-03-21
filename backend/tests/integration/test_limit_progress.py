from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_limit_progress_updates(auth_client: AsyncClient, test_user_with_space):
    """Create limit, add expense, verify progress."""
    space_id = str(test_user_with_space["space"].id)
    cat_id = str(test_user_with_space["category_id"])
    user_id = str(test_user_with_space["user"].id)

    # Create limit
    limit_resp = await auth_client.post(
        f"/api/v1/spaces/{space_id}/limits",
        json={
            "name": "Monthly Test",
            "timeframe": "monthly",
            "threshold_amount": "100.00",
        },
    )
    assert limit_resp.status_code == 201

    # Add expense
    await auth_client.post(
        f"/api/v1/spaces/{space_id}/expenses",
        json={
            "merchant": "Store",
            "purchase_datetime": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "amount": "60.00",
            "category_id": cat_id,
            "spender_id": user_id,
        },
    )

    # Check progress
    limits_resp = await auth_client.get(f"/api/v1/spaces/{space_id}/limits")
    assert limits_resp.status_code == 200
    limits = limits_resp.json()
    assert len(limits) >= 1
    test_limit = [x for x in limits if x["name"] == "Monthly Test"][0]
    assert float(test_limit["spent"]) == 60.0
    assert float(test_limit["progress"]) == 0.6
