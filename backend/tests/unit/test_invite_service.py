import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InviteLink, SpaceMember, User
from app.schemas.space import SpaceCreate
from app.services.invite import generate_invite, join_space
from app.services.space import create_space


@pytest_asyncio.fixture
async def space_with_user(db_session: AsyncSession, test_user: User):
    """Create a space with a test user as member."""
    data = SpaceCreate(name="Test Space", currency_code="USD", timezone="UTC")
    space = await create_space(db_session, test_user, data)
    return space


@pytest.mark.asyncio
async def test_generate_invite(
    db_session: AsyncSession, test_user: User, space_with_user
):
    """Generated invite has a token, correct space, and 7-day expiry."""
    invite = await generate_invite(db_session, space_with_user.id, test_user.id)

    assert invite.token is not None
    assert len(invite.token) > 20
    assert invite.space_id == space_with_user.id
    assert invite.created_by == test_user.id
    assert invite.used_at is None
    # Expiry should be ~7 days from now
    time_until_expiry = invite.expires_at - datetime.now(UTC)
    assert timedelta(days=6) < time_until_expiry < timedelta(days=8)


@pytest.mark.asyncio
async def test_join_space_valid_token(
    db_session: AsyncSession,
    test_user: User,
    second_user: User,
    space_with_user,
):
    """Joining with a valid token adds the user as a member and marks invite used."""
    invite = await generate_invite(db_session, space_with_user.id, test_user.id)

    result = await join_space(db_session, invite.token, second_user.id)

    assert result["space_id"] == space_with_user.id
    assert result["space_name"] == "Test Space"

    # Verify user is now a member
    stmt = select(SpaceMember).where(
        SpaceMember.space_id == space_with_user.id,
        SpaceMember.user_id == second_user.id,
    )
    member_result = await db_session.execute(stmt)
    assert member_result.scalar_one_or_none() is not None

    # Verify invite is marked as used
    invite_stmt = select(InviteLink).where(InviteLink.token == invite.token)
    invite_result = await db_session.execute(invite_stmt)
    used_invite = invite_result.scalar_one()
    assert used_invite.used_at is not None
    assert used_invite.used_by == second_user.id


@pytest.mark.asyncio
async def test_join_space_expired_token(
    db_session: AsyncSession,
    test_user: User,
    second_user: User,
    space_with_user,
):
    """Joining with an expired token raises 410."""
    invite = await generate_invite(db_session, space_with_user.id, test_user.id)

    # Manually expire the invite
    stmt = (
        update(InviteLink)
        .where(InviteLink.id == invite.id)
        .values(expires_at=datetime.now(UTC) - timedelta(hours=1))
    )
    await db_session.execute(stmt)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await join_space(db_session, invite.token, second_user.id)
    assert exc_info.value.status_code == 410
    assert "expired" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_join_space_used_token(
    db_session: AsyncSession,
    test_user: User,
    second_user: User,
    space_with_user,
):
    """Joining with an already-used token raises 410."""
    invite = await generate_invite(db_session, space_with_user.id, test_user.id)

    # Use the token first
    await join_space(db_session, invite.token, second_user.id)

    # Try to use it again with a third user
    third_user = User(
        google_id=f"google_{uuid.uuid4().hex[:12]}",
        email=f"third_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Third User",
    )
    db_session.add(third_user)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        await join_space(db_session, invite.token, third_user.id)
    assert exc_info.value.status_code == 410
    assert "used" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_join_space_already_member(
    db_session: AsyncSession, test_user: User, space_with_user
):
    """Joining a space you're already a member of raises 409."""
    invite = await generate_invite(db_session, space_with_user.id, test_user.id)

    with pytest.raises(HTTPException) as exc_info:
        await join_space(db_session, invite.token, test_user.id)
    assert exc_info.value.status_code == 409
    assert "already" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_join_space_at_member_limit(
    db_session: AsyncSession, test_user: User, space_with_user
):
    """Joining when space has 10 members raises 409."""
    # Add 9 more members to reach the limit (creator is #1)
    for i in range(9):
        user = User(
            google_id=f"google_fill_{i}_{uuid.uuid4().hex[:8]}",
            email=f"fill_{i}_{uuid.uuid4().hex[:8]}@example.com",
            display_name=f"Fill User {i}",
        )
        db_session.add(user)
        await db_session.flush()
        member = SpaceMember(space_id=space_with_user.id, user_id=user.id)
        db_session.add(member)
    await db_session.flush()

    # Now try to join as an 11th member
    eleventh_user = User(
        google_id=f"google_11_{uuid.uuid4().hex[:8]}",
        email=f"eleven_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Eleventh User",
    )
    db_session.add(eleventh_user)
    await db_session.flush()

    invite = await generate_invite(db_session, space_with_user.id, test_user.id)

    with pytest.raises(HTTPException) as exc_info:
        await join_space(db_session, invite.token, eleventh_user.id)
    assert exc_info.value.status_code == 409
    assert "limit" in str(exc_info.value.detail).lower()
