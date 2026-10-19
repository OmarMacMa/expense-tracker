from urllib.parse import parse_qs, urlparse

import pytest
from playwright.async_api import expect

from browser_tests.conftest import authenticate
from tests.insights_support import seed_insights


@pytest.mark.parametrize("width", [390, 1440])
async def test_real_independent_periods(real_db, context, width):
    data = await seed_insights(real_db)
    await authenticate(context, data.partner)
    await context.add_init_script(
        "if (!localStorage.getItem('expense-tracker:period')) "
        "localStorage.setItem('expense-tracker:period', 'this_month')"
    )
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    await page.goto("/insights")
    await page.wait_for_load_state("networkidle")
    header = page.locator("h1").locator("..")
    await expect(header).to_contain_text("$160.00")
    await expect(
        page.get_by_role("button", name="Period: This Month", exact=True)
    ).to_be_visible()
    await page.get_by_role("button", name="Period: This Month", exact=True).click()
    await page.get_by_role("radio", name="Last Month", exact=True).click()
    await expect(header).to_contain_text("$360.00")
    await page.get_by_role("link", name="Home", exact=True).click()
    await page.get_by_role("button", name="Period: This Month", exact=True).click()
    await page.get_by_role("radio", name="This Week", exact=True).click()
    await page.get_by_role("link", name="Insights", exact=True).click()
    await expect(
        page.get_by_role("button", name="Period: Last Month", exact=True)
    ).to_be_visible()
    await page.reload()
    await expect(header).to_contain_text("$360.00")
    await page.get_by_role("button", name="Category: 0 selected").click()
    await page.get_by_role("checkbox", name="Groceries", exact=True).click()
    await expect(
        page.get_by_role("checkbox", name="Groceries", exact=True)
    ).to_be_checked()
    await page.get_by_role("button", name="Category: 1 selected").click()
    await page.wait_for_load_state("networkidle")
    await page.get_by_role("button", name="Period: Last Month", exact=True).click()
    await page.get_by_role("radio", name="This Week", exact=True).click()
    await expect(
        page.get_by_role("button", name="Period: This Week", exact=True)
    ).to_be_visible()
    await expect(
        page.get_by_role("button", name="Category: 1 selected")
    ).to_be_visible()
    await page.wait_for_load_state("networkidle")
    params = {"period": "this_week", "category": str(data.category_id)}
    expected = await context.request.get(
        f"/api/v1/spaces/{data.space.id}/insights/summary", params=params
    )
    assert expected.status == 200
    total = (await expected.json())["total_spent"]
    formatted = await page.evaluate(
        "total => new Intl.NumberFormat('en-US', "
        "{style:'currency',currency:'USD'}).format(Number(total))",
        total,
    )
    await expect(header).to_contain_text(formatted)
    assert parse_qs(urlparse(page.url).query) == {
        "category": [str(data.category_id)],
        "period": ["this_week"],
    }
    await page.get_by_role("link", name="Transactions", exact=True).click()
    await expect(
        page.get_by_role("button", name="Period: This Month", exact=True)
    ).to_be_visible()
    await expect(
        page.get_by_role("button", name="Period: This Month", exact=True)
    ).to_be_visible()
