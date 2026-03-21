import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Expense, Limit, PaymentMethod, Space, SpaceMember


@pytest.mark.asyncio
async def test_seed_creates_data(db_session: AsyncSession):
    """After seeding, all expected data exists."""
    from app.seed import seed_demo_data

    await seed_demo_data(db_session)

    # Check space
    space_result = await db_session.execute(
        select(Space).where(Space.name == "Demo Family")
    )
    space = space_result.scalar_one()
    assert space.currency_code == "USD"

    # Check members (2)
    member_count = await db_session.execute(
        select(func.count()).where(SpaceMember.space_id == space.id)
    )
    assert member_count.scalar_one() == 2

    # Check categories (8 defaults + Uncategorized = 9)
    cat_count = await db_session.execute(
        select(func.count()).where(Category.space_id == space.id)
    )
    assert cat_count.scalar_one() >= 9

    # Check payment methods (Cash + 2 cards = 3)
    pm_count = await db_session.execute(
        select(func.count()).where(PaymentMethod.space_id == space.id)
    )
    assert pm_count.scalar_one() == 3

    # Check expenses (~100, allow some variance)
    exp_count = await db_session.execute(
        select(func.count()).where(Expense.space_id == space.id)
    )
    count = exp_count.scalar_one()
    assert 80 <= count <= 120, f"Expected ~100 expenses, got {count}"

    # Check limits (2)
    limit_count = await db_session.execute(
        select(func.count()).where(Limit.space_id == space.id)
    )
    assert limit_count.scalar_one() == 2


@pytest.mark.asyncio
async def test_seed_idempotent(db_session: AsyncSession):
    """Running seed twice doesn't duplicate data."""
    from app.seed import seed_demo_data

    await seed_demo_data(db_session)
    await seed_demo_data(db_session)

    # Should still have exactly 1 demo space
    space_count = await db_session.execute(
        select(func.count()).where(Space.name == "Demo Family")
    )
    assert space_count.scalar_one() == 1

    # Should still have exactly 2 members
    space_result = await db_session.execute(
        select(Space).where(Space.name == "Demo Family")
    )
    space = space_result.scalar_one()
    member_count = await db_session.execute(
        select(func.count()).where(SpaceMember.space_id == space.id)
    )
    assert member_count.scalar_one() == 2
