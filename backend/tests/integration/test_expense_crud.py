from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_expense_crud_lifecycle(auth_client: AsyncClient, test_user_with_space):
    """Full expense CRUD: create → list → get → update → delete."""
    space_id = str(test_user_with_space["space"].id)
    cat_id = str(test_user_with_space["category_id"])
    user_id = str(test_user_with_space["user"].id)
    base = f"/api/v1/spaces/{space_id}"

    # CREATE
    create_resp = await auth_client.post(
        f"{base}/expenses",
        json={
            "merchant": "Test Store",
            "purchase_datetime": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            "amount": "42.50",
            "category_id": cat_id,
            "spender_id": user_id,
        },
    )
    assert create_resp.status_code == 201
    expense = create_resp.json()
    expense_id = expense["id"]
    assert expense["merchant"] == "Test Store"
    assert expense["total_amount"] == "42.50"

    # LIST
    list_resp = await auth_client.get(f"{base}/expenses")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data["data"]) >= 1

    # GET
    get_resp = await auth_client.get(f"{base}/expenses/{expense_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["merchant"] == "Test Store"

    # UPDATE
    patch_resp = await auth_client.patch(
        f"{base}/expenses/{expense_id}",
        json={
            "amount": "55.00",
            "notes": "Updated note",
        },
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["total_amount"] == "55.00"
    assert patch_resp.json()["notes"] == "Updated note"

    # DELETE
    del_resp = await auth_client.delete(f"{base}/expenses/{expense_id}")
    assert del_resp.status_code == 204

    # Verify gone
    gone_resp = await auth_client.get(f"{base}/expenses/{expense_id}")
    assert gone_resp.status_code == 404
