"""Seed script for demo data. Run with: python -m app.seed"""

import asyncio
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models import (
    Category,
    Expense,
    ExpenseLine,
    Limit,
    LimitFilter,
    Merchant,
    PaymentMethod,
    Space,
    SpaceMember,
    User,
)

DEMO_SPACE_NAME = "Demo Family"

DEFAULT_CATEGORIES = [
    "Groceries",
    "Dining Out",
    "Rent",
    "Utilities",
    "Transportation",
    "Health",
    "Entertainment",
    "Subscriptions",
]

MERCHANTS_BY_CATEGORY = {
    "Groceries": [
        ("Walmart", 12),
        ("Trader Joe's", 8),
        ("Costco", 5),
        ("Whole Foods", 3),
    ],
    "Dining Out": [
        ("Chipotle", 8),
        ("Starbucks", 10),
        ("McDonald's", 4),
        ("Olive Garden", 2),
    ],
    "Rent": [("Landlord LLC", 3)],
    "Utilities": [("Electric Co", 3), ("Water Dept", 3), ("Internet Corp", 3)],
    "Transportation": [("Shell Gas", 6), ("Uber", 4), ("Parking Inc", 3)],
    "Health": [("CVS Pharmacy", 3), ("Dr. Smith", 2)],
    "Entertainment": [("Netflix", 3), ("AMC Theaters", 2), ("Spotify", 3)],
    "Subscriptions": [("Adobe", 3), ("iCloud", 2), ("Gym Membership", 3)],
}

AMOUNT_RANGES = {
    "Groceries": (15, 120),
    "Dining Out": (8, 60),
    "Rent": (1200, 1500),
    "Utilities": (40, 150),
    "Transportation": (10, 80),
    "Health": (15, 200),
    "Entertainment": (10, 50),
    "Subscriptions": (5, 30),
}


async def seed_demo_data(db: AsyncSession) -> None:
    """Create demo data. Idempotent — skips if demo space exists."""
    existing = await db.execute(select(Space).where(Space.name == DEMO_SPACE_NAME))
    if existing.scalar_one_or_none() is not None:
        return

    # Create 2 demo users
    user1 = User(
        google_id="demo_google_user_1",
        email="alice@demo.example.com",
        display_name="Alice Demo",
        avatar_url=None,
    )
    user2 = User(
        google_id="demo_google_user_2",
        email="bob@demo.example.com",
        display_name="Bob Demo",
        avatar_url=None,
    )
    db.add_all([user1, user2])
    await db.flush()

    # Create space
    space = Space(
        name=DEMO_SPACE_NAME,
        currency_code="USD",
        timezone="America/New_York",
        default_tax_pct=Decimal("8.25"),
    )
    db.add(space)
    await db.flush()

    # Add members
    db.add(SpaceMember(space_id=space.id, user_id=user1.id))
    db.add(SpaceMember(space_id=space.id, user_id=user2.id))

    # System records: Uncategorized category + Cash payment method
    uncategorized = Category(
        space_id=space.id,
        name="Uncategorized",
        normalized_name="uncategorized",
        is_system=True,
    )
    db.add(uncategorized)
    cash = PaymentMethod(
        space_id=space.id,
        label="Cash",
        is_system=True,
        owner_id=None,
    )
    db.add(cash)

    # Default categories
    categories: dict[str, Category] = {}
    for cat_name in DEFAULT_CATEGORIES:
        cat = Category(
            space_id=space.id,
            name=cat_name,
            normalized_name=cat_name.lower(),
            is_system=False,
        )
        db.add(cat)
        await db.flush()
        categories[cat_name] = cat

    # Additional payment methods
    visa = PaymentMethod(
        space_id=space.id,
        label="Visa",
        is_system=False,
        owner_id=user1.id,
    )
    mastercard = PaymentMethod(
        space_id=space.id,
        label="Mastercard",
        is_system=False,
        owner_id=user2.id,
    )
    db.add_all([visa, mastercard])
    await db.flush()

    payment_methods = [cash, visa, mastercard]
    users = [user1, user2]

    # Create ~100 expenses over 3 months
    now = datetime.now(UTC)
    random.seed(42)

    for cat_name, merchant_list in MERCHANTS_BY_CATEGORY.items():
        category = categories[cat_name]
        amount_min, amount_max = AMOUNT_RANGES[cat_name]

        for merchant_name, count in merchant_list:
            for _ in range(count):
                days_ago = random.randint(0, 90)
                hours_ago = random.randint(0, 23)
                purchase_dt = now - timedelta(days=days_ago, hours=hours_ago)
                amount = Decimal(str(round(random.uniform(amount_min, amount_max), 2)))
                spender = random.choice(users)
                pm = random.choice(payment_methods)

                expense = Expense(
                    space_id=space.id,
                    merchant=merchant_name,
                    merchant_normalized=merchant_name.lower(),
                    purchase_datetime=purchase_dt,
                    total_amount=amount,
                    spender_id=spender.id,
                    payment_method_id=pm.id,
                    notes=None,
                    status="confirmed",
                )
                db.add(expense)
                await db.flush()

                line = ExpenseLine(
                    expense_id=expense.id,
                    amount=amount,
                    category_id=category.id,
                    line_order=0,
                )
                db.add(line)

                # Upsert merchant
                existing_merchant = await db.execute(
                    select(Merchant).where(
                        Merchant.space_id == space.id,
                        Merchant.normalized_name == merchant_name.lower(),
                    )
                )
                m = existing_merchant.scalar_one_or_none()
                if m is None:
                    m = Merchant(
                        space_id=space.id,
                        name=merchant_name,
                        normalized_name=merchant_name.lower(),
                        last_category_id=category.id,
                        use_count=1,
                    )
                    db.add(m)
                else:
                    m.use_count += 1
                    m.last_category_id = category.id

    await db.flush()

    # Weekly groceries limit
    weekly_limit = Limit(
        space_id=space.id,
        name="Weekly Groceries",
        timeframe="weekly",
        threshold_amount=Decimal("150.00"),
        warning_pct=Decimal("0.6000"),
    )
    db.add(weekly_limit)
    await db.flush()
    db.add(
        LimitFilter(
            limit_id=weekly_limit.id,
            filter_type="category",
            filter_value=str(categories["Groceries"].id),
        )
    )

    # Monthly total limit
    monthly_limit = Limit(
        space_id=space.id,
        name="Monthly Total",
        timeframe="monthly",
        threshold_amount=Decimal("2000.00"),
        warning_pct=Decimal("0.6000"),
    )
    db.add(monthly_limit)

    await db.commit()


async def main() -> None:
    """Entry point for python -m app.seed."""
    async with async_session_factory() as session:
        await seed_demo_data(session)
        print("Seed data created successfully!")


if __name__ == "__main__":
    asyncio.run(main())
