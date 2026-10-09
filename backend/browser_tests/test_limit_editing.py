from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from playwright.async_api import expect
from sqlalchemy import select

from app.models import Category, Expense, ExpenseLine, Limit, LimitFilter
from app.services.time_window import TimeWindowResolver
from browser_tests.conftest import authenticate


@pytest.mark.parametrize("width", [390, 1440])
async def test_timeframe_edit_round_trip(real_db, context, tmp_path, width):
    """Exercise the real Select, PATCH, refetch, reopen and reload journey."""
    actor = await real_db.user("Limit Editor")
    space = await real_db.space(actor, "Limit Editing")
    now = datetime.now(UTC)
    resolver = TimeWindowResolver(space.timezone)
    weekly_start, _ = resolver.get_current_window("weekly", now)
    monthly_start, _ = resolver.get_current_window("monthly", now)
    samples = [
        (now - timedelta(microseconds=1), Decimal("200.40"), "confirmed"),
        (now - timedelta(microseconds=1), Decimal("900"), "pending"),
    ]
    if weekly_start != monthly_start:
        samples.append(
            (
                max(weekly_start, monthly_start) - timedelta(microseconds=1),
                Decimal("100.20"),
                "confirmed",
            )
        )
    expected_pct = {}
    for timeframe in ("weekly", "monthly"):
        start, end = resolver.get_current_window(timeframe, now)
        spent = sum(
            amount
            for when, amount, status in samples
            if status == "confirmed" and start <= when <= end
        )
        expected_pct[timeframe] = f"{spent / Decimal('250.50') * 100:.0f}%"
    async with real_db.sessions() as db:
        category = Category(
            space_id=space.id, name="Groceries", normalized_name="groceries"
        )
        target = Limit(
            space_id=space.id,
            name="Editable Budget",
            timeframe="monthly",
            threshold_amount=Decimal("250.50"),
            warning_pct=Decimal("0.75"),
        )
        control = Limit(
            space_id=space.id,
            name="Other Budget",
            timeframe="monthly",
            threshold_amount=Decimal("900"),
        )
        db.add_all([category, target, control])
        await db.flush()
        db.add(
            LimitFilter(
                limit_id=target.id,
                filter_type="category",
                filter_value=str(category.id),
            )
        )
        for when, amount, status in samples:
            expense = Expense(
                space_id=space.id,
                merchant="Grocer",
                merchant_normalized="grocer",
                purchase_datetime=when,
                total_amount=amount,
                spender_id=actor.id,
                status=status,
            )
            db.add(expense)
            await db.flush()
            db.add(
                ExpenseLine(
                    expense_id=expense.id,
                    amount=amount,
                    category_id=category.id,
                    line_order=0,
                )
            )
        await db.commit()

    await authenticate(context, actor)
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    await page.goto("/home")
    await page.wait_for_load_state("networkidle")
    home_card = page.locator("div.rounded-2xl").filter(
        has=page.get_by_text("Editable Budget", exact=True)
    )
    await expect(
        home_card.get_by_text(expected_pct["monthly"], exact=True)
    ).to_be_visible()
    await page.get_by_role("link", name="Limits", exact=True).click()
    card = page.locator("div.rounded-lg").filter(
        has=page.get_by_role("heading", name="Editable Budget", exact=True)
    )
    for timeframe, label in (("weekly", "Weekly"), ("monthly", "Monthly")):
        await page.get_by_role(
            "button", name="Edit Editable Budget", exact=True
        ).click()
        dialog = page.get_by_role("dialog")
        await dialog.get_by_label("Timeframe", exact=True).click()
        await page.get_by_role("option", name=label, exact=True).click()
        async with page.expect_response(
            lambda response: response.request.method == "PATCH"
            and response.url.endswith(f"/limits/{target.id}")
        ) as saved:
            await dialog.get_by_role("button", name="Update", exact=True).click()
        response = await saved.value
        assert response.status == 200
        assert response.request.post_data_json["timeframe"] == timeframe
        payload = await response.json()
        assert payload["timeframe"] == timeframe
        assert Decimal(payload["threshold_amount"]) == Decimal("250.50")
        assert Decimal(payload["warning_pct"]) == Decimal("0.75")
        assert payload["filters"][0]["filter_value"] == str(category.id)
        await expect(dialog).not_to_be_visible()
        await expect(card.get_by_text(label, exact=True)).to_be_visible()
        await expect(
            card.get_by_text(expected_pct[timeframe], exact=True)
        ).to_be_visible()
        # Return through SPA navigation to exercise the previously populated cache.
        await page.get_by_role("link", name="Home", exact=True).click()
        await expect(
            home_card.get_by_text(expected_pct[timeframe], exact=True)
        ).to_be_visible()
        await page.get_by_role("link", name="Limits", exact=True).click()
        await page.get_by_role(
            "button", name="Edit Editable Budget", exact=True
        ).click()
        await expect(dialog.get_by_label("Timeframe", exact=True)).to_have_text(label)
        await expect(dialog.get_by_label("Threshold ($)", exact=True)).to_have_value(
            "250.50"
        )
        await expect(dialog.get_by_label("Warning at (%)", exact=True)).to_have_value(
            "75"
        )
        await expect(
            dialog.get_by_text("1 category selected", exact=True)
        ).to_be_visible()
        # Unsaved Select changes must not survive closing and reopening.
        await dialog.get_by_label("Timeframe", exact=True).click()
        await page.get_by_role(
            "option", name="Monthly" if timeframe == "weekly" else "Weekly", exact=True
        ).click()
        await dialog.get_by_role("button", name="Cancel", exact=True).click()
        await page.get_by_role(
            "button", name="Edit Editable Budget", exact=True
        ).click()
        await expect(dialog.get_by_label("Timeframe", exact=True)).to_have_text(label)
        await dialog.get_by_role("button", name="Cancel", exact=True).click()
        await page.reload()
        await expect(card.get_by_text(label, exact=True)).to_be_visible()
        async with real_db.sessions() as db:
            assert (await db.get(Limit, target.id)).timeframe == timeframe
            assert (await db.get(Limit, control.id)).timeframe == "monthly"
        await page.screenshot(
            path=str(tmp_path / f"limit-{timeframe}-{width}.png"), full_page=True
        )
    response = await context.request.get(f"/api/v1/spaces/{space.id}/limits")
    assert response.status == 200
    persisted = next(
        item for item in await response.json() if item["id"] == str(target.id)
    )
    assert persisted["timeframe"] == "monthly"
    await page.get_by_role("button", name="Edit Editable Budget", exact=True).click()
    dialog = page.get_by_role("dialog")
    await dialog.get_by_label("Threshold ($)", exact=True).fill("1000000")
    async with page.expect_response(
        lambda response: response.request.method == "PATCH"
        and response.url.endswith(f"/limits/{target.id}")
    ) as rejected:
        await dialog.get_by_role("button", name="Update", exact=True).click()
    assert (await rejected.value).status == 422
    await expect(
        page.get_by_text("Request validation failed", exact=True)
    ).to_be_visible()
    await expect(dialog).to_be_visible()
    await expect(dialog.get_by_label("Threshold ($)", exact=True)).to_have_value(
        "1000000"
    )
    async with real_db.sessions() as db:
        filters = (
            await db.scalars(
                select(LimitFilter).where(LimitFilter.limit_id == target.id)
            )
        ).all()
        assert len(filters) == 1
        assert filters[0].filter_value == str(category.id)
        assert (await db.get(Limit, target.id)).threshold_amount == Decimal("250.50")
