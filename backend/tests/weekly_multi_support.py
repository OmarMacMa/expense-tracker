"""Shared committed data for weekly multi-select API and browser regressions."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models import Category, Expense, ExpenseLine, Merchant, PaymentMethod, Tag
from app.models.expense import expense_line_tags
from app.services.time_window import TimeWindowResolver


async def seed_weekly_multi(database, now: datetime | None = None):
    """Three categories plus one spender contribute 4/8/9/0 matching weeks."""
    now = now or datetime.now(UTC) - timedelta(minutes=1)
    owner = await database.user("Weekly Owner")
    partner = await database.user("Weekly Partner")
    space = await database.space(owner, "Weekly Multi Family")
    await database.member(space, partner)
    resolver = TimeWindowResolver("America/New_York")
    windows = resolver.get_previous_windows("weekly", count=10, ref_date=now)
    async with database.sessions() as db:
        space.timezone = "America/New_York"
        await db.merge(space)
        categories = [
            Category(space_id=space.id, name=name, normalized_name=name.lower())
            for name in ("Weekly A", "Weekly B", "Weekly C", "Zero history")
        ]
        method = PaymentMethod(
            space_id=space.id, label="Weekly Card", owner_id=owner.id
        )
        tags = [
            Tag(space_id=space.id, name=name) for name in ("weekly-red", "weekly-blue")
        ]
        db.add_all(
            [
                *categories,
                method,
                *tags,
                Merchant(
                    space_id=space.id,
                    name="Weekly Match",
                    normalized_name="weekly match",
                ),
                Merchant(
                    space_id=space.id, name="Nonmatching", normalized_name="nonmatching"
                ),
            ]
        )
        await db.flush()

        async def expense(
            when, amount, category, spender, merchant="Weekly Match", status="confirmed"
        ):
            row = Expense(
                space_id=space.id,
                merchant=merchant,
                merchant_normalized=merchant.lower(),
                purchase_datetime=when,
                total_amount=Decimal(amount),
                spender_id=spender,
                payment_method_id=method.id,
                status=status,
            )
            db.add(row)
            await db.flush()
            line = ExpenseLine(
                expense_id=row.id,
                category_id=category.id,
                amount=Decimal(amount),
                line_order=0,
            )
            db.add(line)
            await db.flush()
            for tag in tags:
                await db.execute(
                    expense_line_tags.insert().values(
                        expense_line_id=line.id, tag_id=tag.id
                    )
                )

        for category in categories[:3]:
            await expense(now, "20", category, owner.id)
        # A: four weeks including the ninth; A+B: eight; A+B+C: nine.
        for index in range(9):
            category = categories[
                0 if index in (0, 1, 2, 8) else 1 if index != 7 else 2
            ]
            await expense(
                windows[index][0] + timedelta(hours=1), "100", category, owner.id
            )
            # These must not contribute after the selected spender AND dimensions.
            await expense(
                windows[index][0] + timedelta(hours=2), "500", categories[0], partner.id
            )
            await expense(
                windows[index][0] + timedelta(hours=3),
                "700",
                categories[0],
                owner.id,
                "Nonmatching",
            )
            await expense(
                windows[index][0] + timedelta(hours=4),
                "900",
                categories[0],
                owner.id,
                status="pending",
            )
        await expense(
            windows[9][0] + timedelta(hours=1), "9999", categories[0], owner.id
        )
        await db.commit()
    return {
        "owner": owner,
        "space": space,
        "categories": categories,
        "method": method,
        "windows": windows,
        "now": now,
    }
