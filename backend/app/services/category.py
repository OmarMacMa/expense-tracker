import uuid

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category
from app.models.expense import ExpenseLine
from app.schemas.category import CategoryCreate, CategoryUpdate


async def list_categories(db: AsyncSession, space_id: uuid.UUID) -> list[Category]:
    """Return all categories in the space ordered by name."""
    stmt = select(Category).where(Category.space_id == space_id).order_by(Category.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_category(
    db: AsyncSession, space_id: uuid.UUID, data: CategoryCreate
) -> Category:
    """Create a new user-defined category. Raises 409 on duplicate name."""
    normalized_name = data.name.strip().lower()

    existing = await _find_by_normalized_name(db, space_id, normalized_name)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "DUPLICATE_CATEGORY",
                    "message": f"Category '{data.name}' already exists",
                }
            },
        )

    category = Category(
        space_id=space_id,
        name=data.name.strip(),
        normalized_name=normalized_name,
        is_system=False,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession,
    space_id: uuid.UUID,
    cat_id: uuid.UUID,
    data: CategoryUpdate,
) -> Category:
    """Rename a category. Raises 404 / 409."""
    category = await _get_category(db, space_id, cat_id)

    if category.is_system:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "SYSTEM_ENTITY",
                    "message": "Cannot update system category",
                }
            },
        )

    normalized_name = data.name.strip().lower()
    existing = await _find_by_normalized_name(db, space_id, normalized_name)
    if existing is not None and existing.id != cat_id:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "DUPLICATE_CATEGORY",
                    "message": f"Category '{data.name}' already exists",
                }
            },
        )

    category.name = data.name.strip()
    category.normalized_name = normalized_name
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(
    db: AsyncSession, space_id: uuid.UUID, cat_id: uuid.UUID
) -> None:
    """Delete a category, reassigning its expense lines to Uncategorized."""
    category = await _get_category(db, space_id, cat_id)

    if category.is_system:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "SYSTEM_CATEGORY",
                    "message": "Cannot delete system category",
                }
            },
        )

    # Find the Uncategorized category in the same space
    uncategorized = await _find_by_normalized_name(db, space_id, "uncategorized")
    if uncategorized is None:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "MISSING_SYSTEM_CATEGORY",
                    "message": "Uncategorized category not found",
                }
            },
        )

    # Reassign expense lines then delete — single transaction
    await db.execute(
        update(ExpenseLine)
        .where(ExpenseLine.category_id == cat_id)
        .values(category_id=uncategorized.id)
    )
    await db.delete(category)
    await db.commit()


# ── helpers ──────────────────────────────────────────────────────────


async def _get_category(
    db: AsyncSession, space_id: uuid.UUID, cat_id: uuid.UUID
) -> Category:
    """Fetch a category scoped to space. Raises 404 if missing."""
    stmt = select(Category).where(
        Category.id == cat_id,
        Category.space_id == space_id,
    )
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()
    if category is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Category not found",
                }
            },
        )
    return category


async def _find_by_normalized_name(
    db: AsyncSession, space_id: uuid.UUID, normalized_name: str
) -> Category | None:
    """Find a category by normalized name within a space."""
    stmt = select(Category).where(
        Category.space_id == space_id,
        Category.normalized_name == normalized_name,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
