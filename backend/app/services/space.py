import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, PaymentMethod, Space, SpaceMember, User
from app.schemas.space import SpaceCreate, SpaceUpdate

DEFAULT_CATEGORIES = [
    "Groceries",
    "Dining Out",
    "Rent",
    "Utilities",
    "Transportation",
    "Health",
    "Personal Care",
    "Entertainment",
    "Travel",
    "Gifts",
    "Subscriptions",
]
MAX_MEMBERS = 10


async def create_space(db: AsyncSession, user: User, data: SpaceCreate) -> Space:
    """Create a space with required seed entities."""
    space = Space(
        name=data.name,
        currency_code=data.currency_code,
        timezone=data.timezone,
        default_tax_pct=data.default_tax_pct,
    )
    db.add(space)
    await db.flush()

    # Add creator as member
    member = SpaceMember(space_id=space.id, user_id=user.id)
    db.add(member)

    # Create "Uncategorized" system category
    uncategorized = Category(
        space_id=space.id,
        name="Uncategorized",
        normalized_name="uncategorized",
        is_system=True,
    )
    db.add(uncategorized)

    # Create "Cash" system payment method
    cash = PaymentMethod(
        space_id=space.id,
        label="Cash",
        is_system=True,
        owner_id=None,
    )
    db.add(cash)

    # Optionally seed default categories
    if data.seed_default_categories:
        for cat_name in DEFAULT_CATEGORIES:
            category = Category(
                space_id=space.id,
                name=cat_name,
                normalized_name=cat_name.lower(),
                is_system=False,
            )
            db.add(category)

    await db.commit()
    await db.refresh(space)
    return space


async def get_space(db: AsyncSession, space_id: uuid.UUID) -> Space | None:
    """Get a space by ID."""
    stmt = select(Space).where(Space.id == space_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_space(
    db: AsyncSession, space_id: uuid.UUID, data: SpaceUpdate
) -> Space | None:
    """Update editable space settings. Currency is immutable."""
    space = await get_space(db, space_id)
    if space is None:
        return None

    space.name = data.name
    space.timezone = data.timezone
    space.default_tax_pct = data.default_tax_pct

    await db.commit()
    await db.refresh(space)
    return space


async def list_members(db: AsyncSession, space_id: uuid.UUID) -> list[dict]:
    """List space members with user info."""
    stmt = (
        select(SpaceMember, User)
        .join(User, SpaceMember.user_id == User.id)
        .where(SpaceMember.space_id == space_id)
        .order_by(SpaceMember.joined_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": member.id,
            "user_id": user.id,
            "display_name": user.display_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "joined_at": member.joined_at,
        }
        for member, user in rows
    ]


async def get_member_count(db: AsyncSession, space_id: uuid.UUID) -> int:
    """Get the number of members in a space."""
    stmt = select(func.count()).where(SpaceMember.space_id == space_id)
    result = await db.execute(stmt)
    return result.scalar_one()
