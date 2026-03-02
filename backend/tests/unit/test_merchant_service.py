import pytest
from sqlalchemy import select

from app.models import Category
from app.services.merchant import (
    get_category_suggestion,
    suggest_merchants,
    upsert_merchant,
)


@pytest.mark.asyncio
async def test_suggest_empty(db_session, test_user, test_space):
    results = await suggest_merchants(db_session, test_space.id, "wal")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_suggest_finds_match(db_session, test_user, test_space):
    # Get the Uncategorized category for upsert
    stmt = select(Category).where(
        Category.space_id == test_space.id,
        Category.is_system == True,  # noqa: E712
    )
    result = await db_session.execute(stmt)
    cat = result.scalar_one()

    await upsert_merchant(db_session, test_space.id, "Walmart", cat.id)
    await upsert_merchant(db_session, test_space.id, "Walgreens", cat.id)
    await upsert_merchant(db_session, test_space.id, "Target", cat.id)

    results = await suggest_merchants(db_session, test_space.id, "wal")
    assert len(results) == 2
    names = {m.name for m in results}
    assert "Walmart" in names
    assert "Walgreens" in names


@pytest.mark.asyncio
async def test_upsert_increments_count(db_session, test_user, test_space):
    stmt = select(Category).where(
        Category.space_id == test_space.id,
        Category.is_system == True,  # noqa: E712
    )
    result = await db_session.execute(stmt)
    cat = result.scalar_one()

    m1 = await upsert_merchant(db_session, test_space.id, "Walmart", cat.id)
    assert m1.use_count == 1

    m2 = await upsert_merchant(db_session, test_space.id, "Walmart", cat.id)
    assert m2.use_count == 2


@pytest.mark.asyncio
async def test_category_suggestion(db_session, test_user, test_space):
    stmt = select(Category).where(
        Category.space_id == test_space.id,
        Category.is_system == True,  # noqa: E712
    )
    result = await db_session.execute(stmt)
    cat = result.scalar_one()

    await upsert_merchant(db_session, test_space.id, "Walmart", cat.id)

    suggestion = await get_category_suggestion(db_session, test_space.id, "walmart")
    assert suggestion["last_category_id"] == cat.id
    assert suggestion["last_category_name"] == "Uncategorized"
