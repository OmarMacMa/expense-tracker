import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_non_member_gets_403(auth_client: AsyncClient):
    """Accessing a space you're not a member of returns 403."""
    fake_space_id = str(uuid.uuid4())
    response = await auth_client.get(f"/api/v1/spaces/{fake_space_id}/expenses")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_member_can_access_space(auth_client: AsyncClient, test_user_with_space):
    """Members can access their space."""
    space_id = str(test_user_with_space["space"].id)
    response = await auth_client.get(f"/api/v1/spaces/{space_id}")
    assert response.status_code == 200
    assert response.json()["name"] == test_user_with_space["space"].name
