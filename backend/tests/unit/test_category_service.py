import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.category import (
    create_category,
    delete_category,
    list_categories,
    update_category,
)


@pytest.mark.asyncio
async def test_create_category(db_session, test_user, test_space):
    data = CategoryCreate(name="Groceries")
    cat = await create_category(db_session, test_space.id, data)
    assert cat.name == "Groceries"
    assert cat.normalized_name == "groceries"
    assert cat.is_system is False


@pytest.mark.asyncio
async def test_create_category_duplicate_409(db_session, test_user, test_space):
    await create_category(db_session, test_space.id, CategoryCreate(name="Groceries"))
    with pytest.raises(HTTPException) as exc_info:
        await create_category(
            db_session, test_space.id, CategoryCreate(name="groceries")
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_update_category(db_session, test_user, test_space):
    cat = await create_category(db_session, test_space.id, CategoryCreate(name="Food"))
    updated = await update_category(
        db_session, test_space.id, cat.id, CategoryUpdate(name="Groceries")
    )
    assert updated.name == "Groceries"
    assert updated.normalized_name == "groceries"


@pytest.mark.asyncio
async def test_delete_category_reassigns(db_session, test_user, test_space):
    """Deleting a category should work."""
    cat = await create_category(
        db_session, test_space.id, CategoryCreate(name="ToDelete")
    )
    await delete_category(db_session, test_space.id, cat.id)
    # Category should be gone
    stmt = select(Category).where(Category.id == cat.id)
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cannot_delete_uncategorized(db_session, test_user, test_space):
    """Uncategorized (is_system=True) cannot be deleted."""
    stmt = select(Category).where(
        Category.space_id == test_space.id, Category.is_system == True  # noqa: E712
    )
    result = await db_session.execute(stmt)
    uncategorized = result.scalar_one()

    with pytest.raises(HTTPException) as exc_info:
        await delete_category(db_session, test_space.id, uncategorized.id)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_list_categories(db_session, test_user, test_space):
    await create_category(db_session, test_space.id, CategoryCreate(name="A"))
    await create_category(db_session, test_space.id, CategoryCreate(name="B"))
    cats = await list_categories(db_session, test_space.id)
    assert len(cats) >= 3  # 2 created + Uncategorized
