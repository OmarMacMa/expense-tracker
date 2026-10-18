import re
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect


def open_app(browser, base_url, *, width, authenticated=True):
    context = browser.new_context(viewport={"width": width, "height": 844})
    context.add_init_script(
        "localStorage.setItem('expense-tracker:period', 'this_week')"
    )
    unexpected = []
    errors = []

    def api(route):
        path = urlparse(route.request.url).path
        if path == "/api/v1/auth/me":
            if not authenticated:
                route.fulfill(
                    status=401,
                    json={"detail": {"error": {"code": "UNAUTHORIZED"}}},
                )
                return
            body = {
                "id": "navigation-user",
                "email": "navigation@example.test",
                "display_name": "Navigation Reviewer",
                "avatar_url": None,
                "spaces": [{"id": "navigation-space", "name": "Family Space"}],
            }
        elif path == "/api/v1/spaces/navigation-space":
            body = {
                "id": "navigation-space",
                "name": "Family Space",
                "currency_code": "USD",
                "timezone": "UTC",
                "default_tax_pct": None,
                "created_at": "2026-01-01T00:00:00Z",
            }
        elif path.startswith("/api/v1/spaces/navigation-space/"):
            endpoint = path.rsplit("/", 1)[-1]
            if endpoint == "expenses":
                body = {"data": [], "next_cursor": None}
            elif endpoint == "summary":
                body = {
                    "total_spent": "0",
                    "delta_pct": None,
                    "average_period_count": 0,
                    "period_label": "This Week",
                    "window_start": "2026-01-05T00:00:00Z",
                    "window_end": "2026-01-11T23:59:59Z",
                }
            elif endpoint == "spending-trend":
                body = {
                    "current_series": [
                        {"day": day, "cumulative": "0"} for day in range(1, 8)
                    ],
                    "average_series": [],
                    "average_period_count": 0,
                    "timeframe": "weekly",
                    "year": 2026,
                    "current_day": None,
                }
            elif endpoint in {
                "categories",
                "members",
                "tags",
                "payment-methods",
                "merchants",
                "suggest",
                "category-breakdown",
                "merchant-leaderboard",
                "spender-breakdown",
                "limit-progress",
            }:
                body = []
            else:
                unexpected.append(path)
                route.fulfill(status=500, json={"error": {"message": "Unexpected API"}})
                return
        else:
            unexpected.append(path)
            route.fulfill(status=500, json={"error": {"message": "Unexpected API"}})
            return
        route.fulfill(json=body)

    context.route("**/api/v1/**", api)
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    return context, page, unexpected, errors


@pytest.mark.parametrize(
    "width,target",
    [(390, "space"), (768, "logo"), (1440, "logo"), (1440, "name")],
)
@pytest.mark.parametrize("activation", ["pointer", "keyboard"])
def test_authenticated_brand_returns_home(
    browser, chart_server, artifacts, width, target, activation
):
    context, page, unexpected, errors = open_app(browser, chart_server, width=width)
    documents = []
    page.on(
        "request",
        lambda request: (
            documents.append(request.url)
            if request.resource_type == "document"
            else None
        ),
    )
    try:
        page.goto(f"{chart_server}/transactions")
        page.wait_for_load_state("networkidle")
        expect(
            page.get_by_role("heading", name="Transactions", exact=True)
        ).to_be_visible()
        name = "Family Space — Home" if target == "space" else "Expense Tracker — Home"
        link = page.get_by_role("link", name=name, exact=True)
        expect(link).to_be_visible()
        expect(link).to_have_attribute("href", "/home")
        page.evaluate("window.navigationState = {marker: 'same-document'}")
        context.add_cookies(
            [{"name": "navigation-test", "value": "unchanged", "url": chart_server}]
        )
        if activation == "keyboard":
            page.keyboard.press("Tab")
            expect(link).to_be_focused()
            focus = link.evaluate(
                "el => ({style:getComputedStyle(el).outlineStyle,"
                "width:parseFloat(getComputedStyle(el).outlineWidth)})"
            )
            assert focus["style"] != "none" and focus["width"] >= 2
            page.screenshot(
                path=str(artifacts / f"home-link-focus-{width}-{target}.png"),
                full_page=True,
            )
            page.keyboard.press("Enter")
        elif target == "logo":
            link.locator('[aria-hidden="true"]').click()
        elif target == "name":
            link.get_by_text("Expense Tracker", exact=True).click()
        else:
            link.click()
        expect(page).to_have_url(re.compile(r"/home$"))
        page.wait_for_load_state("networkidle")
        assert len(documents) == 1
        assert page.evaluate("window.navigationState.marker") == "same-document"
        assert (
            page.evaluate("localStorage.getItem('expense-tracker:period')")
            == "this_week"
        )
        assert any(
            cookie["name"] == "navigation-test" and cookie["value"] == "unchanged"
            for cookie in context.cookies()
        )
        assert not unexpected, unexpected
        assert not errors, errors
        if target == "space":
            expect(page.get_by_role("link", name=name, exact=True)).to_have_text(
                "Family Space"
            )
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        # Browser Back proves this is normal router navigation, not a replacement.
        page.go_back()
        expect(page).to_have_url(re.compile(r"/transactions$"))
        expect(link).to_be_visible()
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
def test_public_landing_has_no_authenticated_brand_link(browser, chart_server, width):
    context, page, unexpected, errors = open_app(
        browser, chart_server, width=width, authenticated=False
    )
    try:
        page.goto(chart_server)
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("button", name="Sign in with Google")).to_be_visible()
        expect(page.get_by_role("link", name="Expense Tracker — Home")).to_have_count(0)
        expect(page.get_by_role("link", name="Family Space — Home")).to_have_count(0)
        expect(page).to_have_url(f"{chart_server}/")
        assert not unexpected, unexpected
        assert not errors, errors
    finally:
        context.close()
