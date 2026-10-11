"""Real React/API regressions for repeated daily expense entry."""

import asyncio
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import BrowserContext, Page, Route, expect
from sqlalchemy import select, update

from app.models import Expense, Space, User
from browser_tests.conftest import authenticate
from tests.membership_support import MembershipDatabase


async def setup_entry(
    real_db: MembershipDatabase,
    context: BrowserContext,
    width: int = 1440,
    currency: str = "USD",
) -> tuple[Page, User, Space, str]:
    actor = await real_db.user("Daily Logger")
    space = await real_db.space(actor, "Daily Entry")
    async with real_db.sessions() as db:
        await db.execute(
            update(Space).where(Space.id == space.id).values(currency_code=currency)
        )
        await db.commit()
    await authenticate(context, actor)
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    response = await context.request.post(
        f"/api/v1/spaces/{space.id}/categories", data={"name": "Daily Food"}
    )
    assert response.status == 201
    category_id = (await response.json())["id"]
    await page.goto("/expenses/new")
    await page.wait_for_load_state("networkidle")
    await expect(
        page.get_by_role("button", name="DL Daily Logger", exact=True)
    ).to_be_visible()
    return page, actor, space, category_id


async def choose(page: Page, prompt: str, option: str) -> None:
    await page.get_by_role("button", name=prompt, exact=True).click()
    await page.get_by_role("option", name=option, exact=True).click()


async def fill_entry(page: Page, merchant: str = "Corner Market") -> None:
    await page.get_by_label("Amount", exact=True).fill("12.34")
    await page.get_by_label("Merchant", exact=True).fill(merchant)
    await choose(page, "Select category...", "Daily Food")
    await page.get_by_label("Notes", exact=True).fill("First draft")


async def expenses(real_db: MembershipDatabase, space: Space) -> list[Expense]:
    async with real_db.sessions() as db:
        return list(
            await db.scalars(
                select(Expense)
                .where(Expense.space_id == space.id)
                .order_by(Expense.created_at)
            )
        )


async def screenshot(page: Page, tmp_path: Path, name: str) -> None:
    directory = Path(os.environ.get("BROWSER_ARTIFACTS_DIR", str(tmp_path)))
    directory.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(directory / name), full_page=True)


@pytest.mark.parametrize("width", [390, 1440])
async def test_save_another_reset_defaults_cache_and_second_save(
    real_db: MembershipDatabase, context: BrowserContext, tmp_path: Path, width: int
) -> None:
    symbol = "$" if width == 390 else "€"
    page, actor, space, category_id = await setup_entry(
        real_db, context, width, currency="USD" if width == 390 else "EUR"
    )
    partner = await real_db.user("Other Spender")
    await real_db.member(space, partner)
    # Reload before the draft to load the new member; never reload after a save.
    await page.reload()
    await page.wait_for_load_state("networkidle")
    await fill_entry(page)
    await choose(page, "DL Daily Logger", "OS Other Spender")
    await choose(page, "Select method...", "Cash")
    await page.get_by_label("Time", exact=True).fill("00:01")
    await page.get_by_label("Tags", exact=True).fill("#fresh")
    await page.get_by_label("Tags", exact=True).press("Enter")
    await page.get_by_label("Tags", exact=True).fill("#pending")
    another = page.get_by_role("button", name="Save & Add Another", exact=True)
    await another.scroll_into_view_if_needed()
    await expect(another).to_be_in_viewport()
    await expect(page.get_by_role("button", name="Save Expense")).to_be_in_viewport()
    assert await another.evaluate("(el) => el.getBoundingClientRect().height") >= 44
    assert await page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    await screenshot(page, tmp_path, f"save-another-actions-{width}.png")
    # Repeated blur/focus without typing must not leave an older uncanceled timer.
    await page.evaluate(
        """() => {
          const tag = document.querySelector('input[aria-label="Tags"]');
          tag.blur(); tag.focus(); tag.blur(); tag.focus();
        }"""
    )
    before = datetime.now(UTC)
    async with page.expect_response(
        lambda response: response.request.method == "POST"
        and response.url.endswith("/expenses")
    ) as saved:
        # Keyboard activation must select this action, not ordinary Save.
        await another.focus()
        await another.press("Enter")
    response = await saved.value
    assert response.status == 201
    first = await response.json()
    assert first["merchant"] == "Corner Market"
    assert first["total_amount"] == "12.34"
    assert first["spender"]["id"] == str(partner.id)
    assert first["payment_method_id"] is not None
    assert first["lines"][0]["category_id"] == category_id
    assert {tag["name"] for tag in first["lines"][0]["tags"]} == {"fresh", "pending"}
    await expect(page).to_have_url(re.compile(r"/expenses/new$"))
    await expect(page.get_by_label("Amount", exact=True)).to_be_focused()
    for label in ("Amount", "Merchant", "Tags", "Notes"):
        await expect(page.get_by_label(label, exact=True)).to_have_value("")
    await expect(page.get_by_role("button", name="Select category...")).to_be_visible()
    await expect(page.get_by_role("button", name="Select method...")).to_be_visible()
    await expect(
        page.get_by_role("button", name="DL Daily Logger", exact=True)
    ).to_be_visible()
    await expect(page.get_by_role("alert")).to_have_count(0)
    await expect(page.get_by_text(f"{symbol}0.00", exact=True)).to_be_visible()
    await expect(page.get_by_text("#fresh", exact=True)).to_have_count(0)
    await expect(page.get_by_text("#pending", exact=True)).to_have_count(0)
    now = await page.get_by_label("Time", exact=True).input_value()
    assert now == datetime.now().strftime("%H:%M")
    # Delayed blur must not move focus or reinsert tags after the reset.
    await page.wait_for_timeout(300)
    await expect(page.get_by_label("Amount", exact=True)).to_be_focused()
    await expect(page.get_by_label("Tags", exact=True)).to_have_value("")
    await expect(page.get_by_text("#pending", exact=True)).to_have_count(0)
    assert len(await expenses(real_db, space)) == 1
    await screenshot(page, tmp_path, f"save-another-reset-{width}.png")

    # Reuse the same cached merchant query: it was empty before creation.
    await page.get_by_label("Amount", exact=True).fill("7.89")
    await page.get_by_label("Merchant", exact=True).fill("Corner Market")
    suggestion = page.get_by_role("button", name="Corner Market 1×")
    await expect(suggestion).to_be_visible()
    await suggestion.click()
    await expect(page.get_by_text("Suggested from Corner Market")).to_be_visible()
    await page.get_by_label("Tags", exact=True).fill("#fre")
    await page.get_by_role("button", name="#fresh", exact=True).click()
    async with page.expect_response(
        lambda response: response.request.method == "POST"
        and response.url.endswith("/expenses")
    ) as saved:
        await page.get_by_role("button", name="Save Expense", exact=True).click()
    second = await (await saved.value).json()
    await expect(page).to_have_url(re.compile(r"/transactions$"))
    rows = await expenses(real_db, space)
    assert len(rows) == 2
    assert second["id"] != first["id"]
    assert second["merchant"] == "Corner Market"
    assert second["total_amount"] == "7.89"
    assert second["spender"]["id"] == str(actor.id)
    assert second["payment_method_id"] is None
    assert second["notes"] is None
    assert {tag["name"] for tag in second["lines"][0]["tags"]} == {"fresh"}
    purchase = datetime.fromisoformat(second["purchase_datetime"])
    assert before - timedelta(minutes=1) <= purchase <= datetime.now(UTC)
    # Confirm list and Insights include both real creates, not stale cached data.
    await expect(page.get_by_text("Corner Market", exact=True)).to_have_count(2)
    summary = await context.request.get(
        f"/api/v1/spaces/{space.id}/insights/summary?period=this_month"
    )
    assert summary.status == 200
    assert (await summary.json())["total_spent"] == "20.23"


@pytest.mark.parametrize("action", ["Save Expense", "Save & Add Another"])
@pytest.mark.parametrize("failure", ["network", "server", "validation"])
async def test_failure_preserves_entire_draft(
    real_db: MembershipDatabase,
    context: BrowserContext,
    action: str,
    failure: str,
) -> None:
    page, _, space, _ = await setup_entry(real_db, context)
    merchant = "x" * 101 if failure == "validation" else "Retry Market"
    await fill_entry(page, merchant)
    await choose(page, "Select method...", "Cash")
    await page.get_by_label("Tags", exact=True).fill("#savedtag")
    await page.get_by_label("Tags", exact=True).press("Enter")
    await page.get_by_label("Tags", exact=True).fill("#drafttag")
    time_value = await page.get_by_label("Time", exact=True).input_value()

    async def fail(route: Route) -> None:
        if failure == "network":
            await route.abort("failed")
        else:
            await route.fulfill(
                status=503,
                json={"error": {"code": "SERVICE_UNAVAILABLE", "message": "Try again"}},
            )

    if failure != "validation":
        await page.route(f"**/spaces/{space.id}/expenses", fail)
    # Click directly from tag input so the blur callback is still queued.
    await page.get_by_role("button", name=action, exact=True).click()
    await expect(page.get_by_role("alert")).to_be_visible()
    await expect(page).to_have_url(re.compile(r"/expenses/new$"))
    await page.wait_for_timeout(300)
    for label, value in (
        ("Amount", "12.34"),
        ("Merchant", merchant),
        ("Tags", "#drafttag"),
        ("Notes", "First draft"),
        ("Time", time_value),
    ):
        await expect(page.get_by_label(label, exact=True)).to_have_value(value)
    await expect(page.get_by_text("#savedtag", exact=True)).to_be_visible()
    await expect(page.get_by_role("button", name="Daily Food")).to_be_visible()
    await expect(page.get_by_role("button", name="Cash")).to_be_visible()
    await expect(page.get_by_text("Expense created", exact=True)).to_have_count(0)
    assert await expenses(real_db, space) == []
    await expect(page.get_by_role("button", name=action, exact=True)).to_be_enabled()
    if failure == "validation":
        await page.get_by_label("Merchant", exact=True).fill("Corrected Market")
    else:
        await page.unroute(f"**/spaces/{space.id}/expenses", fail)
    await page.get_by_role("button", name="Save & Add Another").click()
    await expect(page.get_by_label("Amount", exact=True)).to_be_focused()
    await expect(page.get_by_role("alert")).to_have_count(0)
    assert len(await expenses(real_db, space)) == 1


@pytest.mark.parametrize("action", ["Save Expense", "Save & Add Another"])
async def test_concurrent_click_enter_and_both_actions_create_once(
    real_db: MembershipDatabase, context: BrowserContext, action: str
) -> None:
    page, _, space, _ = await setup_entry(real_db, context)
    await fill_entry(page)
    release = asyncio.Event()
    entered = asyncio.Event()
    posts = 0

    async def hold(route: Route) -> None:
        nonlocal posts
        posts += 1
        entered.set()
        await release.wait()
        await route.continue_()

    await page.route(f"**/spaces/{space.id}/expenses", hold)
    await page.evaluate(
        """(action) => {
          const buttons = [...document.querySelectorAll('button')];
          const chosen = buttons.find(b => b.textContent.trim() === action);
          const other = buttons.find(b =>
            b.textContent.trim() === (action === 'Save Expense'
              ? 'Save & Add Another' : 'Save Expense'));
          chosen.click(); chosen.click(); other.click();
          chosen.form.requestSubmit(chosen);
        }""",
        action,
    )
    await asyncio.wait_for(entered.wait(), timeout=5)
    await expect(page.get_by_role("button", name="Saving...")).to_be_disabled()
    await expect(page.get_by_role("button", name="Save & Add Another")).to_be_disabled()
    await expect(page.get_by_label("Amount", exact=True)).to_be_disabled()
    await page.get_by_label("Merchant", exact=True).press("Enter")
    assert posts == 1
    release.set()
    if action == "Save Expense":
        await expect(page).to_have_url(re.compile(r"/transactions$"))
    else:
        await expect(page.get_by_label("Amount", exact=True)).to_be_focused()
    assert posts == 1
    assert len(await expenses(real_db, space)) == 1


async def test_implicit_enter_saves_current_unblurred_merchant(
    real_db: MembershipDatabase, context: BrowserContext
) -> None:
    page, _, space, _ = await setup_entry(real_db, context)
    await fill_entry(page)
    await page.get_by_label("Merchant", exact=True).fill("Keyboard Market")
    await page.get_by_label("Merchant", exact=True).press("Enter")
    await expect(page).to_have_url(re.compile(r"/transactions$"))
    rows = await expenses(real_db, space)
    assert len(rows) == 1
    assert rows[0].merchant == "Keyboard Market"


async def test_delayed_merchant_response_cannot_repopulate_reset(
    real_db: MembershipDatabase, context: BrowserContext
) -> None:
    page, _, space, category_id = await setup_entry(real_db, context)
    await fill_entry(page)
    release = asyncio.Event()
    entered = asyncio.Event()

    async def hold_category(route: Route) -> None:
        entered.set()
        await release.wait()
        await route.fulfill(
            json={
                "name": "Old Merchant",
                "last_category_id": category_id,
                "last_category_name": "Daily Food",
            }
        )

    await page.route("**/merchants/Old%20Merchant/category", hold_category)
    await page.get_by_label("Merchant", exact=True).fill("Old Merchant")
    await page.get_by_label("Merchant", exact=True).press("Tab")
    await asyncio.wait_for(entered.wait(), timeout=5)
    await page.get_by_role("button", name="Save & Add Another").click()
    await expect(page.get_by_label("Amount", exact=True)).to_be_focused()
    release.set()
    await page.wait_for_load_state("networkidle")
    await expect(page.get_by_label("Merchant", exact=True)).to_have_value("")
    await expect(page.get_by_role("button", name="Select category...")).to_be_visible()
    await expect(page.get_by_text("Suggested from Old Merchant")).to_have_count(0)
    assert len(await expenses(real_db, space)) == 1


async def spa_navigate(page: Page, path: str) -> None:
    await page.evaluate(
        "(path) => { history.pushState({}, '', path); "
        "window.dispatchEvent(new PopStateEvent('popstate')); }",
        path,
    )


async def test_saved_expense_refreshes_warm_transactions_and_home_caches(
    real_db: MembershipDatabase, context: BrowserContext
) -> None:
    await context.add_init_script(
        "localStorage.setItem('expense-tracker:period', 'this_month')"
    )
    page, _, space, _ = await setup_entry(real_db, context)
    await spa_navigate(page, "/home")
    await page.wait_for_load_state("networkidle")
    await expect(page.locator("span.text-4xl")).to_have_text("$0.00")
    await spa_navigate(page, "/transactions")
    await page.wait_for_load_state("networkidle")
    await expect(page.get_by_text("Corner Market", exact=True)).to_have_count(0)
    await spa_navigate(page, "/expenses/new")
    await fill_entry(page)
    await page.get_by_role("button", name="Save & Add Another").click()
    await expect(page.get_by_label("Amount", exact=True)).to_be_focused()
    # Remount the same query keys inside staleTime, without a page reload.
    async with page.expect_response(
        lambda response: response.request.method == "GET"
        and "/expenses?" in response.url
    ) as refreshed:
        await spa_navigate(page, "/transactions")
    assert len((await (await refreshed.value).json())["data"]) == 1
    await expect(page.get_by_text("Corner Market", exact=True)).to_have_count(1)
    async with page.expect_response(
        lambda response: "/insights/summary?" in response.url
    ) as refreshed:
        await spa_navigate(page, "/home")
    assert (await (await refreshed.value).json())["total_spent"] == "12.34"
    await expect(page.locator("span.text-4xl")).to_have_text("$12.34")
    assert (
        await page.evaluate("localStorage.getItem('expense-tracker:period')")
        == "this_month"
    )
    assert len(await expenses(real_db, space)) == 1
