"""Committed filter fixtures shared by API and actual browser regressions."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models import Category, PaymentMethod
from app.schemas.expense import ExpenseCreate
from app.services.expense import create_expense
from app.services.time_window import TimeWindowResolver
from tests.membership_support import MembershipDatabase


async def filter_dataset(database: MembershipDatabase) -> dict:
    """Build mixed dimensions, multi-tag expenses, and an isolated other space."""
    actor = await database.user("Filter Owner")
    partner = await database.user("Filter Partner")
    outsider = await database.user("Filter Outsider")
    space = await database.space(actor, "Filter Family")
    other = await database.space(outsider, "Other Filter Family")
    await database.member(space, partner)
    async with database.sessions() as db:
        categories = [
            Category(space_id=space.id, name=name, normalized_name=name.lower())
            for name in ("Dining", "Groceries", "Travel")
        ]
        methods = [
            PaymentMethod(space_id=space.id, label=label, owner_id=actor.id)
            for label in ("Visa", "Debit")
        ]
        db.add_all([*categories, *methods])
        await db.commit()
        other_category = await db.scalar(
            select(Category).where(Category.space_id == other.id)
        )
        other_method = await db.scalar(
            select(PaymentMethod).where(PaymentMethod.space_id == other.id)
        )
        now = datetime.now(UTC) - timedelta(seconds=30)
        for index in range(24):
            await create_expense(
                db,
                space.id,
                ExpenseCreate(
                    amount=Decimal("10"),
                    merchant="Cafe, North" if index % 2 else "Shop %",
                    category_id=categories[index % 3].id,
                    spender_id=actor.id,
                    payment_method_id=methods[index % 2].id,
                    purchase_datetime=now,
                    tags=["red", "blue"],
                ),
                actor.id,
            )
        await create_expense(
            db,
            space.id,
            ExpenseCreate(
                amount=Decimal("90"),
                merchant="Partner Only",
                category_id=categories[0].id,
                spender_id=partner.id,
                payment_method_id=methods[0].id,
                purchase_datetime=now,
                tags=["red"],
            ),
            actor.id,
        )
        pending = await create_expense(
            db,
            space.id,
            ExpenseCreate(
                amount=Decimal("70"),
                merchant="Pending Only",
                category_id=categories[0].id,
                spender_id=actor.id,
                payment_method_id=methods[0].id,
                purchase_datetime=now,
                tags=["red"],
            ),
            actor.id,
        )
        pending.status = "pending"
        await db.commit()
        await create_expense(
            db,
            other.id,
            ExpenseCreate(
                amount=Decimal("999"),
                merchant="Other Space",
                category_id=other_category.id,
                spender_id=outsider.id,
                payment_method_id=other_method.id,
                purchase_datetime=now,
                tags=["red", "blue"],
            ),
            outsider.id,
        )
        previous = TimeWindowResolver("UTC").get_previous_windows("monthly", count=1)[0]
        await create_expense(
            db,
            space.id,
            ExpenseCreate(
                amount=Decimal("30"),
                merchant="Cafe, North",
                category_id=categories[0].id,
                spender_id=actor.id,
                payment_method_id=methods[0].id,
                purchase_datetime=previous[0] + timedelta(hours=1),
                tags=["red", "blue"],
            ),
            actor.id,
        )
    return {
        "actor": actor,
        "partner": partner,
        "outsider": outsider,
        "space": space,
        "categories": categories,
        "methods": methods,
        "other_category": other_category,
        "other_method": other_method,
    }
