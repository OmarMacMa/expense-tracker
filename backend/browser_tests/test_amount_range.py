import re
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.async_api import expect

from browser_tests.conftest import BASE_URL, authenticate
from tests.amount_range_support import range_dataset


def amount_url_pattern(minimum: str, maximum: str) -> re.Pattern:
    checks = "".join(
        f"(?=.*[?&]{key}={re.escape(value)}(?:&|$))" if value else f"(?!.*[?&]{key}=)"
        for key, value in (("min_amount", minimum), ("max_amount", maximum))
    )
    return re.compile(f"^{checks}.*$")


@pytest.mark.parametrize("width", [390, 1440])
async def test_real_range_apply_clear_context_and_precision(
    real_db, context, tmp_path, width
):
    data = await range_dataset(real_db)
    await authenticate(context, data["owner"])
    await context.add_init_script(
        "localStorage.setItem('expense-tracker:period', 'this_month')"
    )
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    await page.goto("/insights")
    await page.wait_for_load_state("networkidle")
    heading = page.get_by_role("heading", name="Insights", exact=True).locator("..")
    # Includes all confirmed current expenses, never the foreign tenant or pending row.
    await expect(heading).to_contain_text("$1,090.31")
    minimum = page.get_by_label("Minimum amount (USD)")
    maximum = page.get_by_label("Maximum amount (USD)")
    assert (await minimum.bounding_box())["width"] >= 128
    assert (await maximum.bounding_box())["width"] >= 128
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    for invalid in ("-1", "NaN", "Infinity", "not-a-number"):
        await minimum.fill(invalid)
        await page.get_by_role("button", name="Apply range", exact=True).click()
        await expect(page.get_by_role("alert")).to_contain_text("finite, nonnegative")
    assert not any("min_amount=" in url or "max_amount=" in url for url in requests)
    await minimum.fill("10.")
    await maximum.fill("20.20")
    await page.get_by_role("button", name="Apply range", exact=True).click()
    await expect(page.get_by_role("alert")).to_contain_text("finite, nonnegative")
    await page.wait_for_load_state("networkidle")
    assert not any("min_amount=" in url or "max_amount=" in url for url in requests)
    await minimum.fill("20.21")
    await page.get_by_role("button", name="Apply range", exact=True).click()
    await expect(page.get_by_role("alert")).to_contain_text("must not exceed")
    assert not any("min_amount=" in url or "max_amount=" in url for url in requests)
    await minimum.fill("10.10")
    async with page.expect_response(
        lambda response: "/insights/summary?" in response.url
        and "min_amount=10.10" in response.url
    ) as summary_response:
        await page.get_by_role("button", name="Apply range", exact=True).click()
    summary = await (await summary_response.value).json()
    assert Decimal(summary["total_spent"]) == Decimal("90.30")
    await page.wait_for_load_state("networkidle")
    await expect(heading).to_contain_text("$90.30")
    await expect(
        page.get_by_role("button", name="Remove applied amount range")
    ).to_contain_text("Amount: USD 10.10 to 20.20")
    assert await page.get_by_text("Range Outlier", exact=True).count() == 0
    assert await page.get_by_text("Foreign", exact=True).count() == 0
    for endpoint in (
        "summary",
        "spending-trend",
        "category-breakdown",
        "merchant-leaderboard",
        "spender-breakdown",
    ):
        urls = [url for url in requests if f"/insights/{endpoint}?" in url]
        assert urls, endpoint
        assert all(
            parse_qs(urlparse(url).query).get("min_amount") == ["10.10"]
            and parse_qs(urlparse(url).query).get("max_amount") == ["20.20"]
            for url in urls
        )
    # Fetch outputs through the same authenticated real API used by the rendered page.
    base = f"/api/v1/spaces/{data['space'].id}"
    params = {"period": "this_month", "min_amount": "10.10", "max_amount": "20.20"}
    for endpoint in ("category-breakdown", "merchant-leaderboard", "spender-breakdown"):
        response = await context.request.get(
            f"{base}/insights/{endpoint}", params=params
        )
        assert response.ok
        assert sum(Decimal(row["total"]) for row in await response.json()) == Decimal(
            "90.30"
        )
    trend = await (
        await context.request.get(f"{base}/insights/spending-trend", params=params)
    ).json()
    assert Decimal(trend["current_series"][-1]["cumulative"]) == Decimal("90.30")
    assert Decimal(trend["average_series"][-1]["cumulative"]) == Decimal("10.10")
    await page.screenshot(
        path=str(tmp_path / f"insights-range-{width}.png"), full_page=True
    )
    assert await page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    await page.get_by_role("link", name="View all transactions").click()
    await expect(
        page.get_by_role("heading", name="Transactions", exact=True, level=1)
    ).to_be_visible()
    await expect(page).to_have_url(re.compile(r"/transactions\?"))
    await expect(page.get_by_label("Minimum amount (USD)")).to_have_value("10.10")
    await expect(page.get_by_label("Maximum amount (USD)")).to_have_value("20.20")
    assert parse_qs(urlparse(page.url).query)["period"] == ["this_month"]
    await page.wait_for_load_state("networkidle")
    await expect(page.get_by_text("Range Medium", exact=True)).to_be_visible()
    assert await page.get_by_text("Range Outlier", exact=True).count() == 0
    await page.get_by_label("Minimum amount (USD)").fill("20.200000000000000001")
    await page.get_by_label("Maximum amount (USD)").fill("20.200000000000000002")
    await page.get_by_role("button", name="Apply range", exact=True).click()
    await expect(
        page.get_by_text("No matching transactions", exact=True)
    ).to_be_visible()
    await page.get_by_role("button", name="Clear amount range", exact=True).click()
    await expect(page.get_by_text("Range Outlier", exact=True)).to_be_visible()
    await expect(page.get_by_label("Minimum amount (USD)")).to_have_value("")
    await page.get_by_label("Minimum amount (USD)").fill("0")
    await page.get_by_label("Maximum amount (USD)").fill("0")
    await page.get_by_role("button", name="Apply range", exact=True).click()
    await expect(
        page.get_by_text("No matching transactions", exact=True)
    ).to_be_visible()
    await page.get_by_role("button", name="Clear all", exact=True).click()
    await expect(page.get_by_text("Range Outlier", exact=True)).to_be_visible()
    await expect(page.get_by_label("Maximum amount (USD)")).to_have_value("")
    await page.screenshot(
        path=str(tmp_path / f"transactions-clear-{width}.png"), full_page=True
    )


async def test_real_insights_one_sided_equal_blank_and_clear(real_db, context):
    data = await range_dataset(real_db)
    await authenticate(context, data["owner"])
    await context.add_init_script(
        "localStorage.setItem('expense-tracker:period', 'this_month')"
    )
    page = await context.new_page()
    await page.goto("/insights")
    await page.wait_for_load_state("networkidle")
    heading = page.get_by_role("heading", name="Insights", exact=True).locator("..")
    for minimum, maximum, expected in (
        ("20.20", "", "$1,020.20"),
        ("", "10.10", "$10.11"),
        ("20.20", "20.20", "$20.20"),
        ("", "0", "$0.00"),
        ("0", "", "$1,090.31"),
        ("", "", "$1,090.31"),
    ):
        await page.get_by_label("Minimum amount (USD)").fill(minimum)
        await page.get_by_label("Maximum amount (USD)").fill(maximum)
        await page.get_by_role("button", name="Apply range", exact=True).click()
        await expect(page).to_have_url(amount_url_pattern(minimum, maximum))
        await expect(heading).to_contain_text(expected)
        await page.wait_for_load_state("networkidle")
    await expect(
        page.get_by_role("button", name="Remove applied amount range")
    ).to_have_count(0)
    await page.get_by_label("Maximum amount (USD)").fill("10.10")
    await page.get_by_role("button", name="Apply range", exact=True).click()
    await expect(heading).to_contain_text("$10.11")
    await page.get_by_role("button", name="Remove applied amount range").click()
    await expect(heading).to_contain_text("$1,090.31")
    await expect(page.get_by_label("Maximum amount (USD)")).to_have_value("")


async def test_real_localized_decimal_input_retains_exact_query(real_db, context):
    data = await range_dataset(real_db)
    browser = context.browser
    assert browser
    localized = await browser.new_context(locale="de-DE", base_url=BASE_URL)
    try:
        await authenticate(localized, data["owner"])
        await localized.add_init_script(
            "localStorage.setItem('expense-tracker:period', 'this_month')"
        )
        page = await localized.new_page()
        await page.goto(f"{BASE_URL}/insights")
        await page.wait_for_load_state("networkidle")
        await page.get_by_label("Minimum amount (USD)").fill("10,100000000000000001")
        await page.get_by_label("Maximum amount (USD)").fill("20,199999999999999999")
        async with page.expect_response(
            lambda response: "/insights/summary?" in response.url
            and "min_amount=10.100000000000000001" in response.url
        ) as result:
            await page.get_by_role("button", name="Apply range", exact=True).click()
        value = await (await result.value).json()
        assert Decimal(value["total_spent"]) == Decimal("60")
        await expect(
            page.get_by_role("button", name="Remove applied amount range")
        ).to_contain_text("10,100000000000000001 to 20,199999999999999999")
    finally:
        await localized.close()


async def test_real_range_failure_is_not_an_empty_success(real_db, context):
    data = await range_dataset(real_db)
    await authenticate(context, data["owner"])
    page = await context.new_page()
    await page.goto("/insights")
    await page.wait_for_load_state("networkidle")

    async def fail_chart(route):
        await route.fulfill(
            status=503,
            content_type="application/json",
            body='{"error":{"code":"UNAVAILABLE","message":"Test outage"}}',
        )

    await page.route("**/insights/category-breakdown?*max_amount=*", fail_chart)
    await page.get_by_label("Maximum amount (USD)").fill("20.20")
    await page.get_by_role("button", name="Apply range", exact=True).click()
    await expect(page.get_by_role("alert")).to_contain_text(
        "Unable to load data", timeout=20000
    )
    assert await page.get_by_text("No category data yet", exact=True).count() == 0
    await page.unroute("**/insights/category-breakdown?*max_amount=*", fail_chart)
    await page.get_by_role("button", name="Retry", exact=True).click()
    await expect(page.get_by_role("alert")).to_have_count(0)
    await expect(page.get_by_text("By Category", exact=True)).to_be_visible()
