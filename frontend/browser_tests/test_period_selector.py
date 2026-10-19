import re
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import expect

from .test_home_navigation import open_app

STORAGE_PREFIX = "expense-tracker:period-override:navigation-user:navigation-space:"


def selector(page, label):
    return page.get_by_role("button", name=f"Period: {label}", exact=True)


def choose_period(page, label):
    page.get_by_role("button", name=re.compile(r"^Period:")).click()
    page.get_by_role("radio", name=label, exact=True).click()
    expect(
        page.get_by_role("dialog", name="Period settings", exact=True)
    ).to_have_count(0)
    page.wait_for_load_state("networkidle")


@pytest.mark.parametrize("width", [390, 1440])
def test_independent_periods_navigation_and_clear(
    browser, chart_server, artifacts, width
):
    context, page, unexpected, errors = open_app(browser, chart_server, width=width)
    requests = []
    page.on(
        "request",
        lambda request: (
            requests.append(request.url) if "/api/v1/spaces/" in request.url else None
        ),
    )
    try:
        page.goto(f"{chart_server}/home")
        page.wait_for_load_state("networkidle")
        expect(selector(page, "This Week")).to_be_visible()
        selector(page, "This Week").click()
        expect(page.get_by_role("radio")).to_have_count(2)
        page.get_by_role("radio", name="This Month", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        assert (
            page.evaluate("localStorage.getItem('expense-tracker:period')")
            == "this_month"
        )
        page.get_by_role("link", name="Insights", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        # Explicitly selecting an already-checked preset saves it for this view.
        choose_period(page, "This Month")
        assert parse_qs(urlparse(page.url).query)["period"] == ["this_month"]
        choose_period(page, "Last Month")
        expect(selector(page, "Last Month")).to_be_visible()
        assert parse_qs(urlparse(page.url).query)["period"] == ["last_month"]
        page.screenshot(
            path=str(artifacts / f"period-insights-override-{width}.png"),
            full_page=True,
        )
        page.get_by_role("link", name="Transactions", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        choose_period(page, "Year to Date")
        expect(selector(page, "Year to Date")).to_be_visible()
        page.get_by_role("link", name="Home", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        choose_period(page, "This Week")
        page.screenshot(
            path=str(artifacts / f"period-home-{width}.png"), full_page=True
        )
        page.get_by_role("link", name="Insights", exact=True).click()
        expect(selector(page, "Last Month")).to_be_visible()
        page.reload()
        expect(selector(page, "Last Month")).to_be_visible()
        page.get_by_role("link", name="Transactions", exact=True).click()
        expect(selector(page, "Year to Date")).to_be_visible()
        page.reload()
        expect(selector(page, "Year to Date")).to_be_visible()
        # Explicit URL context takes priority, without changing the other view.
        page.goto(
            f"{chart_server}/insights?period=last_week&category=one&category=two&min_amount=10.10000000001"
        )
        page.wait_for_load_state("networkidle")
        expect(selector(page, "Last Week")).to_be_visible()
        choose_period(page, "This Month")
        expect(selector(page, "This Month")).to_be_visible()
        query = parse_qs(urlparse(page.url).query)
        assert query["period"] == ["this_month"] and "month" not in query
        assert query["category"] == ["one", "two"]
        assert query["min_amount"] == ["10.10000000001"]
        assert (
            page.evaluate(
                "(key) => localStorage.getItem(key)", STORAGE_PREFIX + "insights"
            )
            == '{"period":"this_month"}'
        )
        page.reload()
        expect(selector(page, "This Month")).to_be_visible()
        page.get_by_role("link", name="Home", exact=True).click()
        choose_period(page, "This Week")
        page.get_by_role("link", name="Insights", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        page.get_by_role("link", name="Transactions", exact=True).click()
        expect(selector(page, "Year to Date")).to_be_visible()
        page.get_by_role("button", name="Clear all", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        page.reload()
        expect(selector(page, "This Month")).to_be_visible()
        assert (
            page.evaluate(
                "(key) => localStorage.getItem(key)", STORAGE_PREFIX + "transactions"
            )
            is None
        )
        page.wait_for_load_state("networkidle")
        assert any(
            parse_qs(urlparse(url).query).get("period") == ["this_month"]
            for url in requests
        )
        assert not unexpected, unexpected
        assert not errors, errors
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
def test_month_selection_keyboard_and_context_retention(
    browser, chart_server, artifacts, width
):
    context, page, unexpected, errors = open_app(
        browser, chart_server, width=width, include_expense=True
    )
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    try:
        page.goto(f"{chart_server}/insights?category=one&category=two&max_amount=20")
        page.wait_for_load_state("networkidle")
        control = selector(page, "This Month")
        control.focus()
        control.press("Enter")
        page.get_by_role("button", name="Choose a month…", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        expect(page.get_by_text("Choose a month to apply", exact=True)).to_be_visible()
        page.get_by_label("Month picker").fill("2026-02")
        expect(selector(page, "This Month")).to_be_visible()
        page.get_by_role("button", name="Apply month", exact=True).click()
        expect(selector(page, "February 2026")).to_be_visible()
        expect(page.get_by_label("Month picker")).to_have_count(0)
        selector(page, "February 2026").click()
        page.get_by_role("button", name="Choose a month…", exact=True).click()
        expect(page.get_by_label("Month picker")).to_have_value("2026-02")
        page.get_by_label("Month picker").fill("2026-03")
        page.keyboard.press("Escape")
        expect(selector(page, "February 2026")).to_be_focused()
        assert parse_qs(urlparse(page.url).query)["month"] == ["2026-02"]
        page.wait_for_load_state("networkidle")
        query = parse_qs(urlparse(page.url).query)
        assert query["month"] == ["2026-02"]
        assert query["period"] == ["this_month"]
        assert query["category"] == ["one", "two"] and query["max_amount"] == ["20"]
        for endpoint in (
            "summary",
            "spending-trend",
            "category-breakdown",
            "merchant-leaderboard",
            "spender-breakdown",
            "expenses",
        ):
            matching = [
                url
                for url in requests
                if urlparse(url).path.endswith("/" + endpoint)
                and parse_qs(urlparse(url).query).get("month") == ["2026-02"]
            ]
            assert matching, endpoint
            assert all(
                parse_qs(urlparse(url).query)["period"] == ["this_month"]
                for url in matching
            )
        expect(page.get_by_test_id("spending-trend-chart")).to_contain_text(
            "February 2026"
        )
        page.get_by_role("button", name="Remove category: one", exact=True).click()
        expect(selector(page, "February 2026")).to_be_visible()
        page.reload()
        expect(selector(page, "February 2026")).to_be_visible()
        page.screenshot(
            path=str(artifacts / f"period-selected-month-{width}.png"), full_page=True
        )
        page.get_by_role("link", name="View all transactions").click()
        expect(
            page.get_by_role("heading", name="Transactions", exact=True)
        ).to_be_visible()
        expect(selector(page, "February 2026")).to_be_visible()
        page.go_back()
        expect(selector(page, "February 2026")).to_be_visible()
        choose_period(page, "Last Week")
        expect(page.get_by_label("Month picker")).to_have_count(0)
        assert "month" not in parse_qs(urlparse(page.url).query)
        choose_period(page, "This Month")
        expect(selector(page, "This Month")).to_be_visible()
        assert not unexpected, unexpected
        assert not errors, errors
    finally:
        context.close()


def test_period_preferences_are_scoped_and_bad_storage_is_ignored(
    browser, chart_server
):
    context, page, unexpected, errors = open_app(browser, chart_server, width=390)
    context.add_init_script(
        """(() => {
          localStorage.setItem('expense-tracker:period-override:another-user:navigation-space:insights',
            JSON.stringify({period:'last_month'}));
          localStorage.setItem('expense-tracker:period-override:navigation-user:another-space:insights',
            JSON.stringify({period:'ytd'}));
          localStorage.setItem('expense-tracker:period-override:navigation-user:navigation-space:insights',
            '{broken');
        })()"""
    )
    try:
        page.goto(f"{chart_server}/insights")
        page.wait_for_load_state("networkidle")
        expect(selector(page, "This Month")).to_be_visible()
        choose_period(page, "Last Month")
        page.get_by_role("link", name="Transactions", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        page.get_by_role("link", name="Insights", exact=True).click()
        expect(selector(page, "Last Month")).to_be_visible()
        assert not unexpected, unexpected
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
def test_home_view_all_overrides_saved_transactions_period(
    browser, chart_server, width
):
    context, page, unexpected, errors = open_app(browser, chart_server, width=width)
    try:
        page.goto(f"{chart_server}/transactions")
        choose_period(page, "Last Month")
        page.get_by_role("link", name="Home", exact=True).click()
        expect(selector(page, "This Week")).to_be_visible()
        page.get_by_role("link", name="View all →", exact=True).click()
        expect(selector(page, "This Week")).to_be_visible()
        assert parse_qs(urlparse(page.url).query)["period"] == ["this_week"]
        page.reload()
        expect(selector(page, "This Week")).to_be_visible()
        assert not unexpected, unexpected
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
def test_saved_period_empty_state_and_independent_default(browser, chart_server, width):
    context, page, unexpected, errors = open_app(browser, chart_server, width=width)
    try:
        page.goto(f"{chart_server}/transactions")
        expect(selector(page, "This Month")).to_be_visible()
        expect(page.get_by_role("heading", name="No transactions yet")).to_be_visible()
        choose_period(page, "Last Month")
        page.goto(f"{chart_server}/transactions")
        expect(selector(page, "Last Month")).to_be_visible()
        expect(
            page.get_by_role("heading", name="No matching transactions")
        ).to_be_visible()
        page.get_by_role("link", name="Home", exact=True).click()
        choose_period(page, "This Month")
        choose_period(page, "This Week")
        page.get_by_role("link", name="Insights", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        page.get_by_role("link", name="Transactions", exact=True).click()
        expect(selector(page, "Last Month")).to_be_visible()
        page.get_by_role("button", name="Clear all", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        expect(page.get_by_role("heading", name="No transactions yet")).to_be_visible()
        assert not unexpected, unexpected
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
def test_compact_period_control_and_keyboard(browser, chart_server, artifacts, width):
    context, page, unexpected, errors = open_app(browser, chart_server, width=width)
    try:
        page.goto(f"{chart_server}/home")
        page.wait_for_load_state("networkidle")
        control = selector(page, "This Week")
        bounds = control.bounding_box()
        assert bounds["height"] == 32
        assert bounds["width"] < 160
        expect(control).not_to_contain_text("Period:")
        expect(page.get_by_text("Default for other views", exact=True)).to_have_count(0)
        control.focus()
        control.press("Space")
        expect(
            page.get_by_role("dialog", name="Period settings", exact=True)
        ).to_be_visible()
        expect(page.get_by_role("radio", name="This Week", exact=True)).to_be_checked()
        popup = page.get_by_role("dialog", name="Period settings", exact=True)
        assert popup.bounding_box()["width"] <= 220
        expect(page.get_by_text("Default for other views", exact=True)).to_have_count(0)
        page.get_by_role("radio", name="This Week", exact=True).focus()
        page.keyboard.press("ArrowDown")
        expect(selector(page, "This Month")).to_be_visible()
        expect(
            page.get_by_role("dialog", name="Period settings", exact=True)
        ).to_have_count(0)
        page.get_by_role("link", name="Insights", exact=True).click()
        choose_period(page, "Last Month")
        control = selector(page, "Last Month")
        spender = page.get_by_role("button", name="Spender: 0 selected", exact=True)
        assert spender.bounding_box()["height"] == 32
        expect(control).to_have_css(
            "background-color",
            spender.evaluate("el => getComputedStyle(el).backgroundColor"),
        )
        expect(
            page.get_by_role("button", name="Use Home period", exact=True)
        ).to_have_count(0)
        # The Period trigger shares a row with the first dimension, not a banner.
        assert control.evaluate(
            "el => Math.abs(el.getBoundingClientRect().y - "
            "el.nextElementSibling.getBoundingClientRect().y) < 1"
        )
        page.screenshot(
            path=str(artifacts / f"period-compact-insights-{width}.png"), full_page=True
        )
        control.click()
        expect(
            page.get_by_role("button", name="Use Home period", exact=True)
        ).to_have_count(0)
        assert popup.bounding_box()["width"] <= 220
        expect(page.get_by_role("dialog", name="Period settings")).to_have_css(
            "opacity", "1"
        )
        page.screenshot(
            path=str(artifacts / f"period-compact-menu-{width}.png"), full_page=True
        )
        page.keyboard.press("Escape")
        expect(control).to_be_focused()
        assert not unexpected, unexpected
        assert not errors, errors
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        context.close()


@pytest.mark.parametrize("width", [320, 390, 501, 768, 1440])
def test_home_hero_amount_period_and_metadata_layout(
    browser, chart_server, artifacts, width
):
    context, page, unexpected, errors = open_app(browser, chart_server, width=width)
    context.route(
        "**/insights/summary?*",
        lambda route: route.fulfill(
            json={
                "total_spent": "1234.56",
                "delta_pct": -12.0,
                "average_period_count": 4,
                "period_label": "This Week",
                "window_start": "2026-01-05T00:00:00Z",
                "window_end": "2026-01-11T23:59:59Z",
            }
        ),
    )
    try:
        page.goto(f"{chart_server}/home")
        page.wait_for_load_state("networkidle")
        amount = page.get_by_text("$1,234.56", exact=True)
        control = selector(page, "This Week")
        description = page.get_by_text("Spent this week", exact=True)
        delta = page.get_by_text("↓ 12.0% vs 4-week avg", exact=True)
        expect(amount).to_be_visible()
        expect(description).to_be_visible()
        expect(delta).to_be_visible()
        number_box = amount.bounding_box()
        control_box = control.bounding_box()
        assert number_box["x"] + number_box["width"] <= control_box["x"]
        assert (
            abs(
                number_box["y"]
                + number_box["height"] / 2
                - control_box["y"]
                - control_box["height"] / 2
            )
            < 1
        )
        label_box = description.bounding_box()
        delta_box = delta.bounding_box()
        assert label_box["y"] >= number_box["y"] + number_box["height"]
        assert delta_box["y"] >= label_box["y"] + label_box["height"]
        assert amount.locator("..").bounding_box()["height"] < 130
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(
            path=str(artifacts / f"hero-compact-{width}.png"), full_page=True
        )
        page.get_by_role("link", name="Transactions", exact=True).click()
        expect(selector(page, "This Month")).to_be_visible()
        page.goto(f"{chart_server}/transactions?period=last_month&category=one")
        chip = page.get_by_role("button", name="Remove category: one", exact=True)
        expect(chip).to_be_visible()
        assert chip.bounding_box()["height"] == 32
        assert (
            page.get_by_role("button", name="Clear all", exact=True).bounding_box()[
                "height"
            ]
            == 32
        )
        assert not unexpected, unexpected
        assert not errors, errors
    finally:
        context.close()
