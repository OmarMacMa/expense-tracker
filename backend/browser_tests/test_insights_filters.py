from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.async_api import expect

from browser_tests.conftest import authenticate
from tests.insights_support import seed_insights


@pytest.mark.parametrize("width", [390, 1440])
async def test_spender_selector_uses_user_id_with_real_backend(
    real_db, context, tmp_path, width
):
    data = await seed_insights(real_db)
    # Partner has exactly one space; owner also has foreign-space test history.
    await authenticate(context, data.partner)
    await context.add_init_script(
        "localStorage.setItem('expense-tracker:period', 'this_month')"
    )
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    responses = []
    page.on("response", lambda response: responses.append(response))
    await page.goto("/insights")
    await page.wait_for_load_state("networkidle")
    assert await page.get_by_role("heading", name="Insights", exact=True).count() == 1
    await page.get_by_role("button", name="Spender: 0 selected").click()
    async with page.expect_response(
        lambda response: "/insights/summary?" in response.url
        and "spender=" in response.url
    ):
        await page.get_by_role("checkbox", name="Alex Spender", exact=True).click()
    await page.keyboard.press("Escape")
    await page.wait_for_load_state("networkidle")
    await page.screenshot(
        path=str(tmp_path / f"selector-ID-{width}.png"), full_page=True
    )
    await expect(page.get_by_text("$135.00", exact=True).first).to_be_visible()
    await page.wait_for_load_state("networkidle")

    prefix = f"/api/v1/spaces/{data.space.id}"
    filtered_responses = {}
    for response in responses:
        parsed = urlparse(response.url)
        query = parse_qs(parsed.query)
        if parsed.path.startswith(prefix) and "spender" in query:
            assert query["spender"] == [str(data.owner.id)]
            assert str(data.membership_id) not in response.url
            assert response.status == 200
            filtered_responses[parsed.path.removeprefix(prefix)] = await response.json()
    assert set(filtered_responses) == {
        "/insights/summary",
        "/insights/spending-trend",
        "/insights/category-breakdown",
        "/insights/merchant-leaderboard",
        "/insights/spender-breakdown",
        "/expenses",
    }
    assert Decimal(filtered_responses["/insights/summary"]["total_spent"]) == 135
    assert (
        Decimal(
            filtered_responses["/insights/spending-trend"]["current_series"][-1][
                "cumulative"
            ]
        )
        == 135
    )
    for endpoint in ("category-breakdown", "merchant-leaderboard", "spender-breakdown"):
        assert (
            sum(
                Decimal(item["total"])
                for item in filtered_responses[f"/insights/{endpoint}"]
            )
            == 135
        )
    expenses = filtered_responses["/expenses"]["data"]
    assert len(expenses) == 3
    assert {expense["spender"]["id"] for expense in expenses} == {str(data.owner.id)}
    assert sum(Decimal(expense["total_amount"]) for expense in expenses) == 135
    assert all(expense["status"] == "confirmed" for expense in expenses)
    await expect(page.get_by_text("$135.00", exact=True).first).to_be_visible()
    assert (
        "No transactions match these filters"
        not in await page.locator("body").inner_text()
    )
    assert "Pending Market" not in await page.locator("body").inner_text()
    for title in ("Spending Trend", "By Category", "Top Merchants", "By Spender"):
        await expect(
            page.get_by_role("heading", name=title, exact=True)
        ).to_be_visible()
    # Recharts uses a 1.5s entrance animation after the response has rendered.
    await page.wait_for_timeout(1700)
    await page.screenshot(path=str(tmp_path / f"spender-{width}.png"), full_page=True)

    # Add category and merchant through real selectors: 2 matching expenses / $100.
    await page.get_by_role("button", name="Category: 0 selected").click()
    await page.get_by_role("checkbox", name="Groceries", exact=True).click()
    await page.keyboard.press("Escape")
    await page.get_by_role("button", name="Merchant: 0 selected").click()
    async with page.expect_response(
        lambda response: "/insights/summary?" in response.url
        and parse_qs(urlparse(response.url).query).get("merchant") == ["Market"]
        and parse_qs(urlparse(response.url).query).get("category")
        == [str(data.category_id)]
        and parse_qs(urlparse(response.url).query).get("spender")
        == [str(data.owner.id)]
    ):
        await page.get_by_role("checkbox", name="Market", exact=True).click()
    await page.keyboard.press("Escape")
    await expect(page.get_by_text("$100.00", exact=True).first).to_be_visible()
    await page.wait_for_load_state("networkidle")
    combined_responses = {}
    for response in responses:
        parsed = urlparse(response.url)
        query = parse_qs(parsed.query)
        if (
            parsed.path.startswith(prefix)
            and query.get("spender") == [str(data.owner.id)]
            and query.get("category") == [str(data.category_id)]
            and query.get("merchant") == ["Market"]
        ):
            assert response.status == 200
            combined_responses[parsed.path.removeprefix(prefix)] = await response.json()
    assert set(combined_responses) == set(filtered_responses)
    assert Decimal(combined_responses["/insights/summary"]["total_spent"]) == 100
    assert (
        Decimal(
            combined_responses["/insights/spending-trend"]["current_series"][-1][
                "cumulative"
            ]
        )
        == 100
    )
    for endpoint in ("category-breakdown", "merchant-leaderboard", "spender-breakdown"):
        assert (
            sum(
                Decimal(item["total"])
                for item in combined_responses[f"/insights/{endpoint}"]
            )
            == 100
        )
    assert {
        expense["id"] for expense in combined_responses["/expenses"]["data"]
    } == data.matching_ids
    assert "Other Store" not in await page.locator("body").inner_text()
    await page.wait_for_timeout(1700)
    await page.screenshot(path=str(tmp_path / f"combined-{width}.png"), full_page=True)
    await page.get_by_role("button", name="Clear all", exact=True).click()
    await expect(page.get_by_text("$160.00", exact=True).first).to_be_visible()
    await page.wait_for_load_state("networkidle")


@pytest.mark.parametrize(
    "endpoint",
    [
        "summary",
        "spending-trend",
        "category-breakdown",
        "merchant-leaderboard",
        "spender-breakdown",
        "expenses",
    ],
)
async def test_failed_queries_are_not_empty_success(real_db, context, endpoint):
    data = await seed_insights(real_db)
    await authenticate(context, data.partner)
    path = "expenses" if endpoint == "expenses" else f"insights/{endpoint}"

    async def fail(route):
        await route.fulfill(
            status=503,
            content_type="application/json",
            body='{"error":{"code":"UNAVAILABLE","message":"Temporary test failure"}}',
        )

    pattern = f"**/api/v1/spaces/{data.space.id}/{path}*"
    await context.route(pattern, fail)
    page = await context.new_page()
    await page.goto("/insights")
    alert = page.get_by_role("alert").filter(has_text="Unable to load data")
    await expect(alert).to_be_visible(timeout=20000)
    assert (
        "No transactions match these filters"
        not in await page.locator("body").inner_text()
    )
    assert "No category data yet" not in await page.locator("body").inner_text()
    if endpoint == "summary":
        await expect(page.get_by_text("$160.00", exact=True)).to_be_visible()
    await context.unroute(pattern, fail)
    await alert.get_by_role("button", name="Retry", exact=True).click()
    await expect(alert).to_have_count(0)
    await page.wait_for_load_state("networkidle")
