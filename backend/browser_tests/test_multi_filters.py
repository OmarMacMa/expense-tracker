import json
import re
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.async_api import expect

from app.services.time_window import TimeWindowResolver
from browser_tests.conftest import authenticate
from tests.filter_support import filter_dataset


async def select_values(page, label, values):
    await page.get_by_role(
        "button", name=re.compile(rf"^{re.escape(label)}: \d+ selected$")
    ).click()
    dialog = page.get_by_role("dialog", name=f"Select {label.lower()}")
    if label == "Category" and len(values) > 1:
        # Several events before the router's next render must still accumulate.
        await dialog.get_by_role("checkbox").evaluate_all(
            "(elements, names) => elements.filter(element => "
            "names.includes(element.closest('label').textContent.trim()))"
            ".forEach(element => element.click())",
            values,
        )
        for value in values:
            await expect(
                dialog.get_by_role("checkbox", name=value, exact=True)
            ).to_be_checked()
        await page.keyboard.press("Escape")
        return
    for value in values:
        checkbox = dialog.get_by_role("checkbox", name=value, exact=True)
        await checkbox.click()
        await expect(checkbox).to_be_checked()
    await page.keyboard.press("Escape")


@pytest.mark.parametrize("width", [390, 1440])
async def test_accumulating_filters_view_all_and_clear(
    real_db, context, tmp_path, width
):
    data = await filter_dataset(real_db)
    await authenticate(context, data["actor"])
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    await page.goto("/insights?period=this_month")
    await page.wait_for_load_state("networkidle")
    await select_values(page, "Category", ["Dining", "Groceries", "Travel"])
    await select_values(page, "Spender", ["Filter Owner"])
    await select_values(page, "Tag", ["#red", "#blue"])
    await select_values(page, "Merchant", ["Cafe, North", "Shop %"])
    await select_values(page, "Payment Method", ["Visa", "Debit"])
    await expect(
        page.get_by_role("button", name="Category: 3 selected")
    ).to_be_visible()
    await expect(page.get_by_role("button", name="Spender: 1 selected")).to_be_visible()
    await page.wait_for_load_state("networkidle")
    params = parse_qs(urlparse(page.url).query)
    assert set(params["category"]) == {str(c.id) for c in data["categories"]}
    assert params["spender"] == [str(data["actor"].id)]
    assert set(params["merchant"]) == {"Cafe, North", "Shop %"}
    # The rendered summary, not just transport, reflects three categories AND owner.
    header = page.locator("h1").locator("..")
    await expect(header).to_contain_text("$240.00")
    await page.get_by_role("button", name="Last Month", exact=True).click()
    await expect(header).to_contain_text("$30.00")
    previous_month = (
        TimeWindowResolver("UTC")
        .get_previous_windows("monthly", count=1)[0][0]
        .strftime("%Y-%m")
    )
    await page.get_by_label("Month picker").fill(previous_month)
    await expect(header).to_contain_text("$30.00")
    assert parse_qs(urlparse(page.url).query)["month"] == [previous_month]
    await page.get_by_role("button", name="This Month", exact=True).click()
    await expect(header).to_contain_text("$240.00")
    assert "month" not in parse_qs(urlparse(page.url).query)
    assert parse_qs(urlparse(page.url).query)["category"] == params["category"]
    await page.wait_for_load_state("networkidle")
    for endpoint in (
        "/insights/summary",
        "/insights/spending-trend",
        "/insights/category-breakdown",
        "/insights/merchant-leaderboard",
        "/insights/spender-breakdown",
        "/expenses",
    ):
        matching = [
            url
            for url in requests
            if endpoint in url
            and len(parse_qs(urlparse(url).query).get("category", [])) == 3
        ]
        assert matching, endpoint
    await page.screenshot(
        path=str(tmp_path / f"multi-filters-{width}.png"), full_page=True
    )
    assert await page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    # Individual removal preserves other dimensions.
    await page.get_by_role("button", name="Remove category: Dining", exact=True).click()
    assert len(parse_qs(urlparse(page.url).query)["category"]) == 2
    assert parse_qs(urlparse(page.url).query)["spender"] == [str(data["actor"].id)]
    # Keyboard checkbox toggling and focus restoration.
    trigger = page.get_by_role("button", name="Category: 2 selected", exact=True)
    await trigger.focus()
    await page.keyboard.press("Enter")
    checkbox = page.get_by_role("checkbox", name="Dining", exact=True)
    await checkbox.focus()
    await page.keyboard.press("Space")
    await expect(checkbox).to_be_checked()
    await page.keyboard.press("Escape")
    await expect(
        page.get_by_role("button", name="Category: 3 selected")
    ).to_be_focused()
    await page.get_by_role("link", name="View all transactions").click()
    await page.wait_for_load_state("networkidle")
    assert urlparse(page.url).path == "/transactions"
    transaction_params = parse_qs(urlparse(page.url).query)
    assert transaction_params["category"] == params["category"]
    assert transaction_params["status"] == ["confirmed"]
    assert transaction_params["merchant"] == params["merchant"]
    # Infinite pagination retains the identical repeated keys and status context.
    await page.get_by_test_id("transaction-pagination").scroll_into_view_if_needed()
    await expect(page.get_by_text("24 transactions", exact=True)).to_be_visible(
        timeout=15000
    )
    paginated = [
        parse_qs(urlparse(url).query)
        for url in requests
        if "/expenses?" in url and "cursor=" in url
    ]
    assert paginated
    assert paginated[-1]["category"] == params["category"]
    assert paginated[-1]["tag"] == params["tag"]
    assert paginated[-1]["status"] == ["confirmed"]
    await page.get_by_role("button", name="Category: 3 selected").click()
    await page.get_by_role("button", name="Clear category", exact=True).click()
    await page.keyboard.press("Escape")
    current = parse_qs(urlparse(page.url).query)
    assert "category" not in current
    assert current["spender"] == params["spender"] and current["tag"] == params["tag"]
    await page.reload()
    await expect(page.get_by_role("button", name="Spender: 1 selected")).to_be_visible()
    await page.get_by_role("button", name="Clear all", exact=True).click()
    assert urlparse(page.url).query == ""


async def test_single_value_cache_keys_and_empty_vs_failure(real_db, context):
    data = await filter_dataset(real_db)
    await authenticate(context, data["actor"])
    page = await context.new_page()
    category = str(data["categories"][0].id)
    await page.goto(f"/insights?period=this_month&category={category}")
    await page.wait_for_load_state("networkidle")
    header = page.locator("h1").locator("..")
    await expect(header).to_contain_text("$170.00")
    await expect(
        page.get_by_role("button", name="Category: 1 selected")
    ).to_be_visible()
    await select_values(page, "Spender", ["Filter Owner"])
    await expect(header).to_contain_text("$80.00")
    # Back to the previous filter combination must not reuse the narrower total.
    await page.get_by_role("button", name="Remove spender: Filter Owner").click()
    await expect(header).to_contain_text("$170.00")
    await select_values(page, "Spender", ["Filter Partner"])
    await expect(header).to_contain_text("$90.00")
    await select_values(page, "Merchant", ["Shop %"])
    await expect(header).to_contain_text("$0.00")
    await expect(
        page.get_by_text("No transactions match these filters")
    ).to_be_visible()
    await page.route(
        "**/api/v1/spaces/*/insights/**",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps(
                {"error": {"code": "UNAVAILABLE", "message": "Test failure"}}
            ),
        ),
    )
    await page.route(
        "**/api/v1/spaces/*/expenses?**",
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body=json.dumps(
                {"error": {"code": "UNAVAILABLE", "message": "Test failure"}}
            ),
        ),
    )
    await page.reload()
    await expect(
        page.get_by_role("alert").filter(has_text="Unable to load data")
    ).to_have_count(6, timeout=15000)
    await expect(page.get_by_role("button", name="Retry", exact=True)).to_have_count(6)
    await expect(
        page.get_by_text("No transactions match these filters")
    ).not_to_be_visible()


async def test_insights_ignores_transactions_only_url_search(real_db, context):
    data = await filter_dataset(real_db)
    await authenticate(context, data["actor"])
    page = await context.new_page()
    responses = {}
    endpoints = {
        "summary",
        "spending-trend",
        "category-breakdown",
        "merchant-leaderboard",
        "spender-breakdown",
        "expenses",
    }

    def record_response(response):
        path = urlparse(response.url).path
        endpoint = path.rsplit("/", 1)[-1]
        if endpoint in endpoints:
            responses[endpoint] = response

    page.on("response", record_response)
    categories = "&".join(f"category={category.id}" for category in data["categories"])
    await page.goto(
        f"/insights?period=this_month&spender={data['actor'].id}"
        f"&{categories}&search=Partner%20Only"
    )
    await page.wait_for_load_state("networkidle")
    await expect(page.locator("h1").locator("..")).to_contain_text("$240.00")
    await expect(page.get_by_label("Search transactions")).not_to_be_visible()
    await expect(
        page.get_by_text("No transactions match these filters")
    ).not_to_be_visible()
    assert set(responses) == endpoints
    results = {}
    for endpoint, response in responses.items():
        assert response.status == 200
        assert "search" not in parse_qs(urlparse(response.url).query), endpoint
        results[endpoint] = await response.json()
    assert results["summary"]["total_spent"] == "240.00"
    assert results["spending-trend"]["current_series"][-1]["cumulative"] == "240.00"
    assert sum(Decimal(item["total"]) for item in results["category-breakdown"]) == 240
    assert (
        sum(Decimal(item["total"]) for item in results["merchant-leaderboard"]) == 240
    )
    assert sum(item["count"] for item in results["merchant-leaderboard"]) == 24
    assert len(results["spender-breakdown"]) == 1
    assert results["spender-breakdown"][0]["total"] == "240.00"
    assert len(results["expenses"]["data"]) == 20
    assert all(
        expense["spender"]["id"] == str(data["actor"].id)
        and expense["merchant"] != "Partner Only"
        for expense in results["expenses"]["data"]
    )
    link = page.get_by_role("link", name="View all transactions")
    assert "search" not in parse_qs(urlparse(await link.get_attribute("href")).query)
    await select_values(page, "Merchant", ["Shop %"])
    await expect(page.locator("h1").locator("..")).to_contain_text("$120.00")
    assert "search" not in parse_qs(urlparse(page.url).query)
    await page.get_by_role("button", name="Remove merchant: Shop %").click()
    await expect(page.locator("h1").locator("..")).to_contain_text("$240.00")
    await link.click()
    await expect(page.get_by_label("Search transactions")).to_have_value("")
    await page.get_by_label("Search transactions").fill("Cafe, North")
    await expect(page.get_by_text("12 transactions", exact=True)).to_be_visible()
    assert parse_qs(urlparse(page.url).query)["search"] == ["Cafe, North"]
    await expect(page.get_by_text("Shop %", exact=True)).not_to_be_visible()
