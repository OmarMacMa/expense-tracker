"""Integration tests for the invite join flow (#18, #54)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.main import app
from app.models import InviteLink, Space, SpaceMember, User


async def _make_user(conn, email_suffix: str = "") -> User:
    """Create a standalone user (no space membership)."""
    session = AsyncSession(bind=conn, expire_on_commit=False)

    async def flush_instead_of_commit() -> None:
        await session.flush()

    session.commit = flush_instead_of_commit  # type: ignore[method-assign]

    try:
        user = User(
            google_id=f"google_{uuid.uuid4().hex[:12]}",
            email=f"join_test_{email_suffix or uuid.uuid4().hex[:8]}@test.com",
            display_name="Join Test User",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    finally:
        await session.close()


async def _make_invite(
    conn,
    space_id: uuid.UUID,
    created_by: uuid.UUID,
    *,
    expired: bool = False,
    used: bool = False,
) -> InviteLink:
    """Create an invite link for a space."""
    session = AsyncSession(bind=conn, expire_on_commit=False)

    async def flush_instead_of_commit() -> None:
        await session.flush()

    session.commit = flush_instead_of_commit  # type: ignore[method-assign]

    try:
        expires_at = (
            datetime.now(UTC) - timedelta(days=1)
            if expired
            else datetime.now(UTC) + timedelta(days=7)
        )
        invite = InviteLink(
            space_id=space_id,
            token=uuid.uuid4().hex,
            created_by=created_by,
            expires_at=expires_at,
            used_at=datetime.now(UTC) if used else None,
            used_by=created_by if used else None,
        )
        session.add(invite)
        await session.commit()
        await session.refresh(invite)
        return invite
    finally:
        await session.close()


async def _make_space(conn, owner: User, name: str = "Target Space") -> Space:
    """Create a space with the given user as the only member."""
    session = AsyncSession(bind=conn, expire_on_commit=False)

    async def flush_instead_of_commit() -> None:
        await session.flush()

    session.commit = flush_instead_of_commit  # type: ignore[method-assign]

    try:
        space = Space(
            name=name,
            currency_code="USD",
            timezone="UTC",
        )
        session.add(space)
        await session.flush()

        member = SpaceMember(space_id=space.id, user_id=owner.id)
        session.add(member)
        await session.commit()
        await session.refresh(space)
        return space
    finally:
        await session.close()


def _client_for(token: str) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": token},
    )


@pytest.mark.asyncio
async def test_join_succeeds_for_user_with_no_space(test_engine, test_user_with_space):
    """A user without a space can join via a valid invite."""
    _engine, conn = test_engine
    inviter = test_user_with_space["user"]
    space = test_user_with_space["space"]

    invite = await _make_invite(conn, space.id, inviter.id)
    joiner = await _make_user(conn, "joiner")

    async with _client_for(create_access_token(joiner.id)) as client:
        response = await client.post(f"/api/v1/spaces/join/{invite.token}")

    assert response.status_code == 200
    body = response.json()
    assert body["space_id"] == str(space.id)
    assert body["space_name"] == space.name


@pytest.mark.asyncio
async def test_preview_returns_target_space_info(test_engine, test_user_with_space):
    """Preview endpoint returns target space info without consuming the invite."""
    _engine, conn = test_engine
    inviter = test_user_with_space["user"]
    space = test_user_with_space["space"]

    invite = await _make_invite(conn, space.id, inviter.id)
    joiner = await _make_user(conn, "joiner_preview")

    async with _client_for(create_access_token(joiner.id)) as client:
        response = await client.get(f"/api/v1/spaces/invites/{invite.token}/preview")

    assert response.status_code == 200
    body = response.json()
    assert body["space_id"] == str(space.id)
    assert body["space_name"] == space.name
    assert body["space_currency_code"] == "USD"


@pytest.mark.asyncio
async def test_preview_does_not_consume_invite(test_engine, test_user_with_space):
    """Calling preview leaves the invite usable for a subsequent join."""
    _engine, conn = test_engine
    inviter = test_user_with_space["user"]
    space = test_user_with_space["space"]

    invite = await _make_invite(conn, space.id, inviter.id)
    joiner = await _make_user(conn, "joiner_preview2")
    token_jwt = create_access_token(joiner.id)

    async with _client_for(token_jwt) as client:
        preview = await client.get(f"/api/v1/spaces/invites/{invite.token}/preview")
        assert preview.status_code == 200
        joined = await client.post(f"/api/v1/spaces/join/{invite.token}")
        assert joined.status_code == 200


@pytest.mark.asyncio
async def test_preview_returns_410_for_expired_invite(
    test_engine, test_user_with_space
):
    """Expired invite returns 410 INVITE_EXPIRED on preview."""
    _engine, conn = test_engine
    inviter = test_user_with_space["user"]
    space = test_user_with_space["space"]

    invite = await _make_invite(conn, space.id, inviter.id, expired=True)
    joiner = await _make_user(conn, "joiner_preview_exp")

    async with _client_for(create_access_token(joiner.id)) as client:
        response = await client.get(f"/api/v1/spaces/invites/{invite.token}/preview")

    assert response.status_code == 410
    assert response.json()["detail"]["error"]["code"] == "INVITE_EXPIRED"


@pytest.mark.asyncio
async def test_preview_returns_404_for_unknown_token(test_engine, test_user_with_space):
    """Unknown invite token returns 404 NOT_FOUND on preview."""
    _engine, conn = test_engine
    joiner = await _make_user(conn, "joiner_preview_nf")

    async with _client_for(create_access_token(joiner.id)) as client:
        response = await client.get("/api/v1/spaces/invites/bogus-token/preview")

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_join_returns_already_member_for_user_in_target_space(
    test_engine, test_user_with_space
):
    """Member of the target space sees ALREADY_MEMBER, not ALREADY_HAS_SPACE."""
    _engine, conn = test_engine
    user = test_user_with_space["user"]
    space = test_user_with_space["space"]

    invite = await _make_invite(conn, space.id, user.id)

    async with _client_for(create_access_token(user.id)) as client:
        response = await client.post(f"/api/v1/spaces/join/{invite.token}")

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "ALREADY_MEMBER"


@pytest.mark.asyncio
async def test_join_returns_already_has_space_for_user_in_another_space(
    test_engine, test_user_with_space
):
    """User who already belongs to another space sees ALREADY_HAS_SPACE."""
    _engine, conn = test_engine
    user_a = test_user_with_space["user"]

    user_b = await _make_user(conn, "userB")
    space_b = await _make_space(conn, user_b, name="Space B")
    invite = await _make_invite(conn, space_b.id, user_b.id)

    async with _client_for(create_access_token(user_a.id)) as client:
        response = await client.post(f"/api/v1/spaces/join/{invite.token}")

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "ALREADY_HAS_SPACE"


@pytest.mark.asyncio
async def test_join_already_has_space_takes_precedence_over_expired(
    test_engine, test_user_with_space
):
    """User-state errors (ALREADY_HAS_SPACE) fire before invite-state errors."""
    _engine, conn = test_engine
    user_a = test_user_with_space["user"]

    user_b = await _make_user(conn, "userB_exp")
    space_b = await _make_space(conn, user_b, name="Space B")
    invite = await _make_invite(conn, space_b.id, user_b.id, expired=True)

    async with _client_for(create_access_token(user_a.id)) as client:
        response = await client.post(f"/api/v1/spaces/join/{invite.token}")

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "ALREADY_HAS_SPACE"


@pytest.mark.asyncio
async def test_join_returns_not_found_for_invalid_token(
    test_engine, test_user_with_space
):
    """Invalid/missing invite token returns 404 NOT_FOUND."""
    _engine, conn = test_engine
    joiner = await _make_user(conn, "joiner_nf")

    async with _client_for(create_access_token(joiner.id)) as client:
        response = await client.post("/api/v1/spaces/join/totally-bogus-token")

    assert response.status_code == 404
    assert response.json()["detail"]["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_join_expired_token_returns_410(test_engine, test_user_with_space):
    """Expired invite returns 410 INVITE_EXPIRED."""
    _engine, conn = test_engine
    inviter = test_user_with_space["user"]
    space = test_user_with_space["space"]

    invite = await _make_invite(conn, space.id, inviter.id, expired=True)
    joiner = await _make_user(conn, "joiner_exp")

    async with _client_for(create_access_token(joiner.id)) as client:
        response = await client.post(f"/api/v1/spaces/join/{invite.token}")

    assert response.status_code == 410
    assert response.json()["detail"]["error"]["code"] == "INVITE_EXPIRED"


@pytest.mark.asyncio
async def test_join_used_token_returns_410(test_engine, test_user_with_space):
    """Used invite returns 410 INVITE_USED."""
    _engine, conn = test_engine
    inviter = test_user_with_space["user"]
    space = test_user_with_space["space"]

    invite = await _make_invite(conn, space.id, inviter.id, used=True)
    joiner = await _make_user(conn, "joiner_used")

    async with _client_for(create_access_token(joiner.id)) as client:
        response = await client.post(f"/api/v1/spaces/join/{invite.token}")

    assert response.status_code == 410
    assert response.json()["detail"]["error"]["code"] == "INVITE_USED"


@pytest.mark.asyncio
async def test_create_space_rejects_if_user_already_has_space(
    auth_client, test_user_with_space
):
    """POST /spaces by a user already in a space returns 409 ALREADY_HAS_SPACE."""
    response = await auth_client.post(
        "/api/v1/spaces",
        json={
            "name": "Second Space",
            "currency_code": "USD",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "ALREADY_HAS_SPACE"
