import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from playwright.async_api import expect
from sqlalchemy import select

from app.models import Category
from app.schemas.category import CategoryCreate
from app.schemas.expense import ExpenseCreate
from app.services.category import create_category
from app.services.expense import create_expense
from app.services.time_window import TimeWindowResolver
from browser_tests.conftest import authenticate


async def seed_history(real_db, count, *, filtered=False):
    user = await real_db.user("Weekly Average")
    space = await real_db.space(user, "Weekly Average Family")
    now = datetime.now(UTC)
    resolver = TimeWindowResolver("UTC")
    current_start, _ = resolver.get_current_window("weekly", now)
    windows = resolver.get_previous_windows("weekly", count=10, ref_date=now)
    included = list(range(count - 1)) + [8] if count else []
    async with real_db.sessions() as db:
        category = await create_category(
            db, space.id, CategoryCreate(name="Matching history")
        )
        no_history = await create_category(
            db, space.id, CategoryCreate(name="No history")
        )
        other = await db.scalar(
            select(Category).where(Category.space_id == space.id, Category.is_system)
        )
        purchases = [(current_start, category.id, "50")]
        purchases.extend(
            (windows[index][0] + timedelta(days=2), category.id, "100")
            for index in included
        )
        purchases.append((windows[9][0], category.id, "9000"))
        if filtered:
            purchases.extend(
                (windows[index][0], other.id, "200")
                for index in range(9)
                if index not in included
            )
            purchases.append((current_start, no_history.id, "40"))
        for when, category_id, amount in purchases:
            await create_expense(
                db,
                space.id,
                ExpenseCreate(
                    merchant="Weekly Store",
                    purchase_datetime=when,
                    amount=Decimal(amount),
                    category_id=category_id,
                    spender_id=user.id,
                ),
                user.id,
            )
    return user


async def assert_average(page, count):
    if count:
        await expect(page.get_by_text(f"{count}-week avg", exact=True)).to_be_visible()
        await expect(
            page.get_by_text(re.compile(rf"% vs {count}-week avg$"))
        ).to_be_visible()
        await expect(page.locator(".recharts-line-curve")).to_have_count(1)
    else:
        await expect(page.get_by_text(re.compile(r"\d+-week avg"))).to_have_count(0)
        await expect(page.locator(".recharts-line-curve")).to_have_count(0)


@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("count", [0, 4, 8, 9])
async def test_real_weekly_labels_home_and_insights(
    real_db, context, tmp_path, width, count
):
    user = await seed_history(real_db, count)
    await authenticate(context, user)
    await context.add_init_script(
        "localStorage.setItem('expense-tracker:period', 'this_week')"
    )
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    for route in ("/home", "/insights"):
        await page.goto(route)
        await page.wait_for_load_state("networkidle")
        # Inspect the live rendered state before making assertions.
        assert "spending trend" in (await page.locator("body").inner_text()).lower()
        await assert_average(page, count)
        await page.screenshot(
            path=str(tmp_path / f"{route[1:]}-{width}-{count}.png"), full_page=True
        )
    await page.get_by_role("button", name="Last Week", exact=True).click()
    await page.wait_for_load_state("networkidle")
    await expect(page.get_by_text("Today", exact=True)).to_have_count(0)


@pytest.mark.parametrize("width", [390, 1440])
async def test_real_category_filter_changes_weekly_contributors(
    real_db, context, tmp_path, width
):
    user = await seed_history(real_db, 4, filtered=True)
    await authenticate(context, user)
    await context.add_init_script(
        "localStorage.setItem('expense-tracker:period', 'this_week')"
    )
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    await page.goto("/insights")
    await page.wait_for_load_state("networkidle")
    await assert_average(page, 9)
    category = page.get_by_role("combobox").filter(has_text="Category")
    await category.click()
    await page.get_by_role("option", name="Matching history", exact=True).click()
    await page.wait_for_load_state("networkidle")
    await assert_average(page, 4)
    await page.get_by_role("combobox").filter(has_text="Matching history").click()
    await page.get_by_role("option", name="No history", exact=True).click()
    await page.wait_for_load_state("networkidle")
    await assert_average(page, 0)
    await page.screenshot(
        path=str(tmp_path / f"filtered-no-history-{width}.png"), full_page=True
    )
