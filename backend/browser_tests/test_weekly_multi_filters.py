from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.async_api import expect

from browser_tests.conftest import authenticate
from browser_tests.test_multi_filters import select_values
from tests.weekly_multi_support import seed_weekly_multi


@pytest.mark.parametrize("width", [390, 1440])
async def test_weekly_multi_contributors_and_surface_agreement(
    real_db, context, tmp_path, width
):
    data = await seed_weekly_multi(real_db)
    await authenticate(context, data["owner"])
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    received = []
    page.on("response", lambda response: received.append(response))

    async def surface_data(categories):
        responses = {}
        for response in received:
            parsed = urlparse(response.url)
            query = parse_qs(parsed.query)
            endpoint = parsed.path.rsplit("/", 1)[-1]
            if (
                endpoint
                in (
                    "summary",
                    "spending-trend",
                    "category-breakdown",
                    "merchant-leaderboard",
                    "spender-breakdown",
                    "expenses",
                )
                and set(query.get("category", []))
                == {str(category.id) for category in categories}
                and query.get("spender") == [str(data["owner"].id)]
                and query.get("merchant") == ["Weekly Match"]
                and set(query.get("tag", [])) == {"weekly-red", "weekly-blue"}
                and query.get("payment_method") == [str(data["method"].id)]
            ):
                assert response.status == 200
                responses[endpoint] = await response.json()
        assert set(responses) == {
            "summary",
            "spending-trend",
            "category-breakdown",
            "merchant-leaderboard",
            "spender-breakdown",
            "expenses",
        }
        return responses

    await page.goto("/insights?period=this_week")
    await page.wait_for_load_state("networkidle")
    await select_values(page, "Category", ["Weekly A", "Weekly B", "Weekly C"])
    await select_values(page, "Spender", ["Weekly Owner"])
    await select_values(page, "Merchant", ["Weekly Match"])
    await select_values(page, "Tag", ["#weekly-red", "#weekly-blue"])
    async with page.expect_response(
        lambda response: "/insights/spending-trend?" in response.url
        and "payment_method=" in response.url
    ):
        await select_values(page, "Payment Method", ["Weekly Card"])
    await page.wait_for_load_state("networkidle")
    header = page.locator("h1").locator("..")
    await expect(header).to_contain_text("$60.00")
    await expect(page.get_by_text("9-week avg", exact=True)).to_be_visible()
    responses = await surface_data(data["categories"][:3])
    assert responses["summary"]["average_period_count"] == 9
    assert responses["spending-trend"]["average_period_count"] == 9
    assert (
        Decimal(responses["spending-trend"]["current_series"][-1]["cumulative"]) == 60
    )
    for endpoint in ("category-breakdown", "merchant-leaderboard", "spender-breakdown"):
        assert sum(Decimal(item["total"]) for item in responses[endpoint]) == 60
    assert (
        sum(Decimal(item["total_amount"]) for item in responses["expenses"]["data"])
        == 60
    )
    assert (
        Decimal(responses["spending-trend"]["average_series"][-1]["cumulative"]) == 100
    )
    for category, count, total in (
        ("Weekly C", 8, "$40.00"),
        ("Weekly B", 4, "$20.00"),
    ):
        await page.get_by_role(
            "button", name=f"Remove category: {category}", exact=True
        ).click()
        await expect(page.get_by_text(f"{count}-week avg", exact=True)).to_be_visible()
        await expect(header).to_contain_text(total)
        await page.wait_for_load_state("networkidle")
        responses = await surface_data(data["categories"][: 2 if count == 8 else 1])
        assert responses["summary"]["average_period_count"] == count
        assert responses["spending-trend"]["average_period_count"] == count
        assert (
            Decimal(responses["spending-trend"]["average_series"][-1]["cumulative"])
            == 100
        )
    await page.get_by_role(
        "button", name="Remove category: Weekly A", exact=True
    ).click()
    await expect(
        page.get_by_role("button", name="Category: 0 selected", exact=True)
    ).to_be_visible()
    async with page.expect_response(
        lambda response: "/insights/spending-trend?" in response.url
        and str(data["categories"][3].id) in response.url
    ):
        await select_values(page, "Category", ["Zero history"])
    await page.wait_for_load_state("networkidle")
    await expect(header).to_contain_text("$0.00")
    await expect(page.locator(".recharts-line-curve")).to_have_count(0)
    responses = await surface_data(data["categories"][3:])
    assert responses["summary"]["average_period_count"] == 0
    assert responses["summary"]["delta_pct"] is None
    assert responses["spending-trend"]["average_period_count"] == 0
    assert responses["spending-trend"]["average_series"] == []
    await expect(page.get_by_text("9-week avg", exact=True)).to_have_count(0)
    await expect(page.get_by_text("4-week avg", exact=True)).to_have_count(0)
    await expect(page.locator(".recharts-line-curve")).to_have_count(0)
    await page.screenshot(
        path=str(tmp_path / f"weekly-multi-zero-{width}.png"), full_page=True
    )
