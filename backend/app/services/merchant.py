import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Merchant

SUGGEST_LIMIT = 10


async def suggest_merchants(
    db: AsyncSession, space_id: uuid.UUID, query: str
) -> Sequence[Merchant]:
    """Autocomplete merchants by prefix match on normalized_name.

    Ordered by use_count DESC, limited to 10 results.
    """
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    stmt = (
        select(Merchant)
        .where(
            Merchant.space_id == space_id,
            Merchant.normalized_name.startswith(normalized_query),
        )
        .order_by(Merchant.use_count.desc())
        .limit(SUGGEST_LIMIT)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_category_suggestion(
    db: AsyncSession, space_id: uuid.UUID, merchant_name: str
) -> dict:
    """Get the last category used for a merchant.

    Returns dict with name, last_category_id, last_category_name.
    """
    normalized = merchant_name.strip().lower()

    stmt = select(Merchant).where(
        Merchant.space_id == space_id,
        Merchant.normalized_name == normalized,
    )
    result = await db.execute(stmt)
    merchant = result.scalar_one_or_none()

    if merchant is None or merchant.last_category_id is None:
        return {
            "name": merchant_name,
            "last_category_id": None,
            "last_category_name": None,
        }

    # Fetch category name
    cat_stmt = select(Category).where(Category.id == merchant.last_category_id)
    cat_result = await db.execute(cat_stmt)
    category = cat_result.scalar_one_or_none()

    return {
        "name": merchant.name,
        "last_category_id": merchant.last_category_id,
        "last_category_name": category.name if category else None,
    }


async def upsert_merchant(
    db: AsyncSession,
    space_id: uuid.UUID,
    merchant_name: str,
    category_id: uuid.UUID,
) -> Merchant:
    """Upsert merchant: create if new, update use_count and last_category if existing.

    Called during expense creation (Phase 6).
    """
    import datetime

    normalized = merchant_name.strip().lower()

    stmt = select(Merchant).where(
        Merchant.space_id == space_id,
        Merchant.normalized_name == normalized,
    )
    result = await db.execute(stmt)
    merchant = result.scalar_one_or_none()

    if merchant is None:
        merchant = Merchant(
            space_id=space_id,
            name=merchant_name.strip(),
            normalized_name=normalized,
            last_category_id=category_id,
            use_count=1,
            last_used_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(merchant)
    else:
        merchant.use_count += 1
        merchant.last_category_id = category_id
        merchant.last_used_at = datetime.datetime.now(datetime.UTC)

    await db.flush()
    return merchant
