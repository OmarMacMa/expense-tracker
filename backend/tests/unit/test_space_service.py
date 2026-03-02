import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, PaymentMethod, SpaceMember, User
from app.schemas.space import SpaceCreate, SpaceUpdate
from app.services.space import (
    DEFAULT_CATEGORIES,
    create_space,
    list_members,
    update_space,
)


@pytest.mark.asyncio
async def test_create_space_basic(db_session: AsyncSession, test_user: User):
    """Creating a space returns a valid Space object."""
    data = SpaceCreate(
        name="Family Budget",
        currency_code="USD",
        timezone="America/New_York",
    )
    space = await create_space(db_session, test_user, data)

    assert space.id is not None
    assert space.name == "Family Budget"
    assert space.currency_code == "USD"
    assert space.timezone == "America/New_York"


@pytest.mark.asyncio
async def test_create_space_creator_is_member(
    db_session: AsyncSession, test_user: User
):
    """Creator is automatically added as a member."""
    data = SpaceCreate(name="Test", currency_code="EUR", timezone="UTC")
    space = await create_space(db_session, test_user, data)

    stmt = select(SpaceMember).where(
        SpaceMember.space_id == space.id,
        SpaceMember.user_id == test_user.id,
    )
    result = await db_session.execute(stmt)
    member = result.scalar_one_or_none()
    assert member is not None


@pytest.mark.asyncio
async def test_create_space_seeds_uncategorized(
    db_session: AsyncSession, test_user: User
):
    """Uncategorized category is created with is_system=True."""
    data = SpaceCreate(name="Test", currency_code="USD", timezone="UTC")
    space = await create_space(db_session, test_user, data)

    stmt = select(Category).where(
        Category.space_id == space.id,
        Category.normalized_name == "uncategorized",
    )
    result = await db_session.execute(stmt)
    cat = result.scalar_one_or_none()

    assert cat is not None
    assert cat.is_system is True
    assert cat.name == "Uncategorized"


@pytest.mark.asyncio
async def test_create_space_seeds_cash(db_session: AsyncSession, test_user: User):
    """Cash payment method is created with is_system=True and no owner."""
    data = SpaceCreate(name="Test", currency_code="USD", timezone="UTC")
    space = await create_space(db_session, test_user, data)

    stmt = select(PaymentMethod).where(
        PaymentMethod.space_id == space.id,
        PaymentMethod.label == "Cash",
    )
    result = await db_session.execute(stmt)
    pm = result.scalar_one_or_none()

    assert pm is not None
    assert pm.is_system is True
    assert pm.owner_id is None


@pytest.mark.asyncio
async def test_create_space_with_default_categories(
    db_session: AsyncSession, test_user: User
):
    """Seeding default categories creates 12 total (11 defaults + Uncategorized)."""
    data = SpaceCreate(
        name="Test",
        currency_code="USD",
        timezone="UTC",
        seed_default_categories=True,
    )
    space = await create_space(db_session, test_user, data)

    stmt = select(Category).where(Category.space_id == space.id)
    result = await db_session.execute(stmt)
    categories = result.scalars().all()

    assert len(categories) == len(DEFAULT_CATEGORIES) + 1  # +1 for Uncategorized


@pytest.mark.asyncio
async def test_create_space_without_default_categories(
    db_session: AsyncSession, test_user: User
):
    """Without seeding, only Uncategorized is created."""
    data = SpaceCreate(
        name="Test",
        currency_code="USD",
        timezone="UTC",
        seed_default_categories=False,
    )
    space = await create_space(db_session, test_user, data)

    stmt = select(Category).where(Category.space_id == space.id)
    result = await db_session.execute(stmt)
    categories = result.scalars().all()

    assert len(categories) == 1
    assert categories[0].normalized_name == "uncategorized"


@pytest.mark.asyncio
async def test_update_space(db_session: AsyncSession, test_user: User):
    """Update changes name and timezone but not currency."""
    data = SpaceCreate(name="Old Name", currency_code="USD", timezone="UTC")
    space = await create_space(db_session, test_user, data)

    update_data = SpaceUpdate(name="New Name", timezone="America/Chicago")
    updated = await update_space(db_session, space.id, update_data)

    assert updated is not None
    assert updated.name == "New Name"
    assert updated.timezone == "America/Chicago"
    assert updated.currency_code == "USD"  # unchanged


@pytest.mark.asyncio
async def test_list_members(db_session: AsyncSession, test_user: User):
    """List members returns creator with user info."""
    data = SpaceCreate(name="Test", currency_code="USD", timezone="UTC")
    space = await create_space(db_session, test_user, data)

    members = await list_members(db_session, space.id)

    assert len(members) == 1
    assert members[0]["user_id"] == test_user.id
    assert members[0]["display_name"] == "Test User"
    assert members[0]["email"] == test_user.email
