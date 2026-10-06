from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models import Category, Expense, ExpenseLine, PaymentMethod, Tag
from app.models.expense import expense_line_tags
from app.services.time_window import TimeWindowResolver
from tests.membership_support import MembershipDatabase


async def range_dataset(database: MembershipDatabase) -> dict:
    """Committed, tenant-isolated data shared by API and real browser regressions."""
    owner = await database.user("Range Owner")
    other = await database.user("Other Spender")
    space = await database.space(owner, "Range Family")
    foreign = await database.space(other, "Foreign Family")
    await database.member(space, other)
    resolver = TimeWindowResolver("UTC")
    start, _ = resolver.get_current_window("monthly")
    history = resolver.get_previous_windows("monthly", count=3)
    ids = {}
    async with database.sessions() as db:
        category = await db.scalar(
            select(Category).where(Category.space_id == space.id)
        )
        foreign_category = await db.scalar(
            select(Category).where(Category.space_id == foreign.id)
        )
        alternate = Category(
            space_id=space.id, name="Other", normalized_name="other", is_system=False
        )
        method = PaymentMethod(space_id=space.id, owner_id=owner.id, label="Range Card")
        tag = Tag(space_id=space.id, name="range")
        db.add_all([alternate, method, tag])
        await db.flush()

        async def expense(
            name,
            amount,
            when,
            *,
            target=space,
            spender=owner,
            cat=category,
            tagged=True,
            payment=True,
            status="confirmed",
            split=False,
        ):
            row = Expense(
                space_id=target.id,
                merchant=name,
                merchant_normalized=name.lower(),
                total_amount=Decimal(amount),
                purchase_datetime=when,
                spender_id=spender.id,
                payment_method_id=method.id if payment else None,
                status=status,
            )
            db.add(row)
            await db.flush()
            ids[name] = row.id
            for index in range(2 if split else 1):
                line = ExpenseLine(
                    expense_id=row.id,
                    amount=Decimal(amount) / (2 if split else 1),
                    category_id=cat.id,
                    line_order=index,
                )
                db.add(line)
                await db.flush()
                if tagged:
                    await db.execute(
                        expense_line_tags.insert().values(
                            expense_line_id=line.id, tag_id=tag.id
                        )
                    )

        current = min(
            start + timedelta(days=1), datetime.now(UTC) - timedelta(minutes=1)
        )
        await expense("Range Small", "10.10", current)
        await expense("Range Medium", "20.20", current, split=True)
        await expense("Range Outlier", "1000", current)
        await expense("Tiny", "0.01", current, tagged=False, payment=False)
        await expense(
            "Foreign",
            "15",
            current,
            target=foreign,
            spender=other,
            cat=foreign_category,
            tagged=False,
            payment=False,
        )
        # Each mismatch proves another dimension remains ANDed with amount.
        await expense("Wrong spender", "15", current, spender=other)
        await expense("Wrong category", "15", current, cat=alternate)
        await expense("Wrong tag", "15", current, tagged=False)
        await expense("Wrong method", "15", current, payment=False)
        await expense("Pending", "1000", current, status="pending")
        for index, (previous, _) in enumerate(history):
            await expense(f"History {index}", "10.10", previous + timedelta(days=1))
            await expense(
                f"History outlier {index}", "1000", previous + timedelta(days=1)
            )
        await db.commit()
        return {
            "owner": owner,
            "space": space,
            "foreign": foreign,
            "ids": ids,
            "filters": {
                "status": "confirmed",
                "period": "this_month",
                "spender": str(owner.id),
                "category": str(category.id),
                "tag": "range",
                "payment_method": str(method.id),
            },
        }
