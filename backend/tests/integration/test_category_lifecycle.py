import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_category_create_and_delete(
    auth_client: AsyncClient, test_user_with_space
):
    """Create category, delete it, verify Uncategorized can't be deleted."""
    space_id = str(test_user_with_space["space"].id)
    base = f"/api/v1/spaces/{space_id}/categories"

    # Create
    create_resp = await auth_client.post(base, json={"name": "Groceries"})
    assert create_resp.status_code == 201
    cat_id = create_resp.json()["id"]

    # Delete
    del_resp = await auth_client.delete(f"{base}/{cat_id}")
    assert del_resp.status_code == 204

    # Can't delete Uncategorized
    list_resp = await auth_client.get(base)
    uncat = [c for c in list_resp.json() if c["is_system"]][0]
    fail_resp = await auth_client.delete(f"{base}/{uncat['id']}")
    assert fail_resp.status_code == 422
