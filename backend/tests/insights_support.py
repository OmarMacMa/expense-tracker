"""Shared real-data fixture for Insights API and selector regressions."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models import Category, PaymentMethod, Space, SpaceMember, User
from app.schemas.expense import ExpenseCreate
from app.services.expense import create_expense
from app.services.time_window import TimeWindowResolver
from tests.membership_support import MembershipDatabase


@dataclass
class InsightsData:
    owner: User
    partner: User
    space: Space
    other_space: Space
    membership_id: uuid.UUID
    category_id: uuid.UUID
    other_category_id: uuid.UUID
    payment_method_id: uuid.UUID
    matching_ids: set[str]

    @property
    def combined_filters(self) -> dict[str, str]:
        return {
            "period": "this_month",
            "spender": str(self.owner.id),
            "category": str(self.category_id),
            "merchant": "mArKeT",
            "tag": "#HOUSEHOLD",
            "payment_method": str(self.payment_method_id),
        }


async def seed_insights(database: MembershipDatabase) -> InsightsData:
    """Create two members, matching and distracting expenses, and another space."""
    owner = await database.user("Alex Spender")
    partner = await database.user("Sam Spender")
    outsider = await database.user("Other Space Owner")
    space = await database.space(owner, "Filter Family")
    other_space = await database.space(outsider, "Isolated Family")
    await database.member(space, partner)
    async with database.sessions() as db:
        stored_space = await db.get(Space, space.id)
        stored_space.timezone = "America/Los_Angeles"
        category = Category(
            space_id=space.id, name="Groceries", normalized_name="groceries"
        )
        db.add(category)
        await db.flush()
        other_category = await db.scalar(
            select(Category).where(
                Category.space_id == space.id, Category.is_system.is_(True)
            )
        )
        cash = await db.scalar(
            select(PaymentMethod).where(
                PaymentMethod.space_id == space.id, PaymentMethod.is_system.is_(True)
            )
        )
        membership = await db.scalar(
            select(SpaceMember).where(
                SpaceMember.space_id == space.id, SpaceMember.user_id == owner.id
            )
        )
        assert other_category and cash and membership
        await db.commit()

        resolver = TimeWindowResolver(stored_space.timezone)
        start, _ = resolver.get_current_window("monthly")
        # Also valid on the first day of the local month.
        purchase = min(datetime.now(UTC), start + timedelta(hours=12))
        matching_ids = set()
        for user, merchant, amount, cat, tags, method in (
            (owner, "Market", "60", category.id, ["household"], cash.id),
            (owner, "Market", "40", category.id, ["household"], cash.id),
            (partner, "Market", "25", category.id, ["household"], cash.id),
            (owner, "Other Store", "35", other_category.id, ["travel"], None),
        ):
            expense = await create_expense(
                db,
                space.id,
                ExpenseCreate(
                    merchant=merchant,
                    amount=Decimal(amount),
                    purchase_datetime=purchase,
                    category_id=cat,
                    tags=tags,
                    payment_method_id=method,
                    spender_id=user.id,
                ),
                owner.id,
            )
            if user.id == owner.id and merchant == "Market":
                matching_ids.add(str(expense.id))

        pending = await create_expense(
            db,
            space.id,
            ExpenseCreate(
                merchant="Pending Market",
                amount=Decimal("1000"),
                purchase_datetime=purchase,
                category_id=category.id,
                tags=["household"],
                payment_method_id=cash.id,
                spender_id=owner.id,
            ),
            owner.id,
        )
        pending.status = "pending"
        await db.commit()

        previous_start, _ = resolver.get_previous_windows("monthly", count=1)[0]
        for user, amount in ((owner, "60"), (partner, "300")):
            await create_expense(
                db,
                space.id,
                ExpenseCreate(
                    merchant="Market",
                    amount=Decimal(amount),
                    purchase_datetime=previous_start + timedelta(hours=12),
                    category_id=category.id,
                    tags=["household"],
                    payment_method_id=cash.id,
                    spender_id=user.id,
                ),
                owner.id,
            )
        # Same spender and merchant in another space must never leak.
        await database.member(other_space, owner)
        foreign_category = await db.scalar(
            select(Category).where(Category.space_id == other_space.id)
        )
        assert foreign_category
        await create_expense(
            db,
            other_space.id,
            ExpenseCreate(
                merchant="Market",
                amount=Decimal("500"),
                purchase_datetime=purchase,
                category_id=foreign_category.id,
                tags=["household"],
                spender_id=owner.id,
            ),
            owner.id,
        )
        space.timezone = stored_space.timezone
        return InsightsData(
            owner=owner,
            partner=partner,
            space=space,
            other_space=other_space,
            membership_id=membership.id,
            category_id=category.id,
            other_category_id=other_category.id,
            payment_method_id=cash.id,
            matching_ids=matching_ids,
        )
