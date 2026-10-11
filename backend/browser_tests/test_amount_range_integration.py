from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.async_api import expect

from browser_tests.conftest import authenticate
from browser_tests.test_multi_filters import select_values
from tests.amount_range_support import weekly_range_dataset


@pytest.mark.parametrize("width", [390, 1440])
async def test_integrated_range_arrays_history_navigation_and_clear(
    real_db, context, tmp_path, width
):
    data = await weekly_range_dataset(real_db)
    await authenticate(context, data["owner"])
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    await page.goto("/insights?period=this_week&search=does-not-match")
    await page.wait_for_load_state("networkidle")
    await select_values(page, "Category", ["Weekly A", "Weekly B", "Weekly C"])
    await select_values(page, "Spender", ["Weekly Owner"])
    await select_values(page, "Merchant", ["Weekly Match"])
    await select_values(page, "Tag", ["#weekly-red", "#weekly-blue"])
    await select_values(page, "Payment Method", ["Weekly Card"])
    await page.wait_for_load_state("networkidle")
    header = page.locator("h1").locator("..")
    await expect(header).to_contain_text("$540.00")
    await expect(page.get_by_text("9-week avg", exact=True)).to_be_visible()
    received = []
    page.on("response", lambda response: received.append(response))
    for maximum, count in (("299.99", 8), ("199.99", 4), ("99.99", 0)):
        await page.get_by_label("Minimum amount (USD)").fill("0")
        await page.get_by_label("Maximum amount (USD)").fill(maximum)
        async with page.expect_response(
            lambda response: "/insights/spending-trend?" in response.url
            and parse_qs(urlparse(response.url).query).get("max_amount") == [maximum]
        ):
            await page.get_by_role("button", name="Apply range", exact=True).click()
        await page.wait_for_load_state("networkidle")
        await expect(header).to_contain_text("$540.00")
        if count:
            await expect(
                page.get_by_text(f"{count}-week avg", exact=True)
            ).to_be_visible()
        else:
            await expect(page.get_by_text("4-week avg", exact=True)).to_have_count(0)
            await expect(header).not_to_contain_text("vs")
        outputs = {}
        for response in received:
            query = parse_qs(urlparse(response.url).query)
            endpoint = urlparse(response.url).path.rsplit("/", 1)[-1]
            if query.get("max_amount") == [maximum] and endpoint in (
                "summary",
                "spending-trend",
                "category-breakdown",
                "merchant-leaderboard",
                "spender-breakdown",
                "expenses",
            ):
                assert response.status == 200
                assert len(query["category"]) == 3
                assert query["spender"] == [str(data["owner"].id)]
                assert query["merchant"] == ["Weekly Match"]
                assert set(query["tag"]) == {"weekly-red", "weekly-blue"}
                assert query["payment_method"] == [str(data["method"].id)]
                assert "search" not in query
                outputs[endpoint] = await response.json()
        assert len(outputs) == 6
        assert (
            outputs["summary"]["average_period_count"]
            == outputs["spending-trend"]["average_period_count"]
            == count
        )
        assert Decimal(outputs["summary"]["total_spent"]) == 540
        assert (
            Decimal(outputs["spending-trend"]["current_series"][-1]["cumulative"])
            == 540
        )
        for endpoint in (
            "category-breakdown",
            "merchant-leaderboard",
            "spender-breakdown",
        ):
            assert sum(Decimal(item["total"]) for item in outputs[endpoint]) == 540
        assert all(
            item["status"] == "confirmed" for item in outputs["expenses"]["data"]
        )
        if not count:
            assert outputs["summary"]["delta_pct"] is None
            assert outputs["spending-trend"]["average_series"] == []
        await expect(
            page.get_by_role("status").filter(has_text="Updating insights")
        ).to_have_count(0)
        await page.screenshot(
            path=str(tmp_path / f"range-integrated-{count}-week-{width}.png"),
            full_page=True,
        )
    # Apply range and category removal use the latest URL state in both directions.
    await page.get_by_role(
        "button", name="Remove category: Weekly C", exact=True
    ).click()
    await expect(page.get_by_label("Maximum amount (USD)")).to_have_value("99.99")
    query = parse_qs(urlparse(page.url).query)
    assert len(query["category"]) == 2
    assert query["max_amount"] == ["99.99"]
    await select_values(page, "Category", ["Weekly C"])
    await page.get_by_label("Maximum amount (USD)").fill("50.123456789")
    await page.get_by_role(
        "button", name="Remove category: Weekly C", exact=True
    ).click()
    await expect(
        page.get_by_role("button", name="Category: 2 selected")
    ).to_be_visible()
    await expect(page.get_by_label("Maximum amount (USD)")).to_have_value(
        "50.123456789"
    )
    assert parse_qs(urlparse(page.url).query)["max_amount"] == ["99.99"]
    await select_values(page, "Category", ["Weekly C"])
    await page.get_by_role("button", name="Clear amount range", exact=True).click()
    await expect(page.get_by_text("9-week avg", exact=True)).to_be_visible()
    query = parse_qs(urlparse(page.url).query)
    assert len(query["category"]) == 3 and "max_amount" not in query
    await page.get_by_label("Minimum amount (USD)").fill("20")
    await page.get_by_label("Maximum amount (USD)").fill("20")
    async with page.expect_response(
        lambda response: "/insights/summary?" in response.url
        and parse_qs(urlparse(response.url).query).get("min_amount") == ["20"]
        and parse_qs(urlparse(response.url).query).get("max_amount") == ["20"]
    ):
        await page.get_by_role("button", name="Apply range", exact=True).click()
    await page.wait_for_load_state("networkidle")
    await expect(
        page.get_by_role("status").filter(has_text="Updating insights")
    ).to_have_count(0)
    await page.screenshot(
        path=str(tmp_path / f"range-integrated-insights-{width}.png"), full_page=True
    )
    await page.get_by_role("link", name="View all transactions").click()
    await expect(
        page.get_by_role("heading", name="Transactions", level=1)
    ).to_be_visible()
    query = parse_qs(urlparse(page.url).query)
    assert len(query["category"]) == 3
    assert len(query["tag"]) == 2
    assert query["min_amount"] == query["max_amount"] == ["20"]
    assert query["status"] == ["confirmed"]
    assert "search" not in query
    await page.reload()
    await expect(page.get_by_label("Minimum amount (USD)")).to_have_value("20")
    await expect(
        page.get_by_role("button", name="Category: 3 selected")
    ).to_be_visible()
    # Exercise the actual cursor query through the visible infinite-scroll sentinel.
    for _ in range(3):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_load_state("networkidle")
    await expect(page.locator("h1").locator("..")).to_contain_text("27 transactions")
    responses = [
        response
        for response in received
        if "/expenses?" in response.url and "cursor=" in response.url
    ]
    assert responses
    for response in responses:
        query = parse_qs(urlparse(response.url).query)
        assert len(query["category"]) == 3
        assert query["min_amount"] == query["max_amount"] == ["20"]
        assert query["status"] == ["confirmed"]
    await page.get_by_role("button", name="Remove applied amount range").click()
    await expect(
        page.get_by_role("button", name="Category: 3 selected")
    ).to_be_visible()
    await expect(page.get_by_label("Minimum amount (USD)")).to_have_value("")
    await page.get_by_role("button", name="Clear all", exact=True).click()
    await expect(
        page.get_by_role("button", name="Category: 0 selected")
    ).to_be_visible()
    await expect(page.get_by_label("Maximum amount (USD)")).to_have_value("")
    assert await page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    await page.screenshot(
        path=str(tmp_path / f"range-integrated-clear-{width}.png"), full_page=True
    )
