import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect


def trend(days, current_day, *, year=2026, amount=12.5, count=3):
    timeframe = "weekly" if days == 7 else "yearly" if days >= 365 else "monthly"
    return {
        "current_series": [
            {"day": day, "cumulative": f"{day * amount:.2f}"}
            for day in range(1, days + 1)
        ],
        "average_series": (
            [
                {"day": day, "cumulative": f"{day * amount * 2:.2f}"}
                for day in range(1, days + 1)
            ]
            if count and timeframe != "yearly"
            else []
        ),
        "timeframe": timeframe,
        "year": year,
        "current_day": current_day,
        "average_period_count": count if timeframe != "yearly" else 0,
    }


def open_chart(
    browser, chart_server, *, width, view, data, period=None, baseline=False
):
    period = period or ("this_week" if data["timeframe"] == "weekly" else "this_month")
    context = browser.new_context(viewport={"width": width, "height": 1000})
    errors, unknown = [], []
    context.add_init_script(
        f"localStorage.setItem('expense-tracker:period', {json.dumps(period)})"
    )

    def api(route):
        path = urlparse(route.request.url).path
        endpoint = path.rsplit("/", 1)[-1]
        if path == "/api/v1/auth/me":
            body = {
                "id": "chart-user",
                "email": "chart@example.test",
                "display_name": "Chart Reviewer",
                "avatar_url": None,
                "spaces": [{"id": "chart-space", "name": "Chart Family"}],
            }
        elif path == "/api/v1/spaces/chart-space":
            body = {
                "id": "chart-space",
                "name": "Chart Family",
                "currency_code": "EUR",
                "timezone": "UTC",
                "default_tax_pct": None,
                "created_at": "2026-01-01T00:00:00Z",
            }
        elif endpoint == "spending-trend":
            body = data
        elif endpoint == "summary":
            body = {
                "total_spent": "123.45",
                "delta_pct": None,
                "period_label": period,
                "window_start": "2026-01-01T00:00:00Z",
                "window_end": "2026-12-31T23:59:59Z",
            }
        elif endpoint == "expenses":
            body = {"data": [], "next_cursor": None}
        elif endpoint in {
            "category-breakdown",
            "merchant-leaderboard",
            "spender-breakdown",
            "limit-progress",
            "categories",
            "members",
            "tags",
            "payment-methods",
            "merchants",
            "suggest",
        }:
            body = []
        else:
            unknown.append(path)
            route.fulfill(
                status=500, json={"error": {"message": "Unexpected mock request"}}
            )
            return
        route.fulfill(json=body)

    context.route("**/api/v1/**", api)
    if baseline:

        def original_label_position(route):
            response = route.fetch()
            source = response.text()
            assert "insideTopLeft" in source and "insideTopRight" in source
            source = re.sub(r"offset:\s*6", "offset: 5", source, count=1)
            route.fulfill(
                response=response,
                body=source.replace("insideTopLeft", "top").replace(
                    "insideTopRight", "top"
                ),
            )

        context.route(
            "**/src/components/charts/spending-trend-chart.tsx", original_label_position
        )
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"{chart_server}/{view}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=60000)
    page.evaluate("document.fonts.ready")
    if data["timeframe"] == "yearly":
        page.get_by_role("button", name="YTD", exact=True).click()
        page.wait_for_load_state("networkidle")
    elif view == "insights" and period in {"last_week", "last_month"}:
        page.get_by_role(
            "button",
            name="Last Week" if period == "last_week" else "Last Month",
            exact=True,
        ).click()
        page.wait_for_load_state("networkidle")
    chart = page.get_by_test_id("spending-trend-chart")
    try:
        expect(chart.locator(".recharts-area-curve")).to_be_attached(timeout=15000)
    except AssertionError:
        if artifacts := os.environ.get("CHART_ARTIFACTS"):
            Path(artifacts, "failed-page.html").write_text(
                page.content(), encoding="utf-8"
            )
            Path(artifacts, "failed-errors.json").write_text(json.dumps(errors))
            page.screenshot(
                path=str(Path(artifacts, "failed-page.png")), full_page=True
            )
        context.close()
        raise
    # Recharts animates paths; measure the settled SVG, not an intermediate frame.
    page.wait_for_timeout(1700)
    assert not unknown, unknown
    assert not errors, errors
    return context, page, chart


def geometry(chart):
    return chart.evaluate(
        """chart => {
      const svg = chart.querySelector('svg.recharts-surface');
      const bounds = svg.getBoundingClientRect();
      const rect = element => {
        const r = element.getBoundingClientRect();
        return {x:r.x-bounds.x, y:r.y-bounds.y, width:r.width, height:r.height};
      };
      const label = [...chart.querySelectorAll('text')].find(t => t.textContent === 'Today');
      const marker = chart.querySelector('.recharts-reference-line-line');
      const area = chart.querySelector('.recharts-area-curve');
      const average = chart.querySelector('.recharts-line-curve');
      const ticks = [...chart.querySelectorAll('.recharts-xAxis-tick-labels text')];
      return {
        width: bounds.width, height: bounds.height,
        label: label ? rect(label) : null,
        labelStyle: label ? {fontSize: label.getAttribute('font-size'),
                            fill:label.getAttribute('fill')} : null,
        markerX: marker ? Number(marker.getAttribute('x1')) : null,
        ticks: ticks.map(t => ({text:t.textContent, anchorX:Number(t.getAttribute('x')), ...rect(t)})),
        areaEnd: area.getPointAtLength(area.getTotalLength()).x,
        averageEnd: average ? average.getPointAtLength(average.getTotalLength()).x : null,
        paths: [...chart.querySelectorAll('path')].map(p=>p.getAttribute('d')),
        yLabels: [...chart.querySelectorAll('.recharts-yAxis-tick-labels text')].map(rect)
      };
    }"""
    )


def assert_geometry(chart, data):
    g = geometry(chart)
    assert g["height"] == 200
    assert all(not re.search(r"NaN|Infinity", path or "") for path in g["paths"])
    for rect in g["ticks"] + g["yLabels"]:
        assert rect["x"] >= -0.5, g
        assert rect["x"] + rect["width"] <= g["width"] + 0.5, g
    current_day = data.get("current_day")
    if current_day is None:
        assert g["label"] is None and g["markerX"] is None
    else:
        r = g["label"]
        assert r is not None, g
        assert r["x"] >= 0 and r["y"] >= 0, g
        assert r["x"] + r["width"] <= g["width"], g
        assert r["y"] + r["height"] <= g["height"], g
        assert g["labelStyle"] == {"fontSize": "10", "fill": "var(--muted-foreground)"}
        assert abs(g["areaEnd"] - g["markerX"]) < 0.5, g
    if data["average_series"]:
        assert g["averageEnd"] is not None
        if current_day and current_day < len(data["current_series"]):
            assert g["averageEnd"] > g["areaEnd"], g
    if data["timeframe"] != "yearly":
        positions = [tick["anchorX"] for tick in g["ticks"]]
        gaps = [b - a for a, b in zip(positions, positions[1:])]
        assert len(gaps) >= 1
        assert max(gaps) - min(gaps) < 0.5, g
        if data["timeframe"] == "weekly":
            assert [tick["text"] for tick in g["ticks"]] == [
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
                "Sun",
            ]
        else:
            ticks = [int(tick["text"]) for tick in g["ticks"]]
            steps = [b - a for a, b in zip(ticks, ticks[1:])]
            assert len(set(steps)) == 1
        first_x = positions[0]
        last_x = g["averageEnd"] if data["average_series"] else g["areaEnd"]
        if current_day and data["average_series"]:
            expected_x = first_x + (current_day - 1) / (
                len(data["current_series"]) - 1
            ) * (last_x - first_x)
            assert abs(g["markerX"] - expected_x) < 0.5, g
    else:
        names = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        months = [names.index(tick["text"]) for tick in g["ticks"]]
        assert len(set(b - a for a, b in zip(months, months[1:]))) == 1
    return g


@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("view", ["home", "insights"])
@pytest.mark.parametrize("days", [7, 28, 29, 30, 31])
@pytest.mark.parametrize("edge", ["first", "last"])
def test_today_and_uniform_axis(
    browser, chart_server, artifacts, width, view, days, edge
):
    data = trend(
        days, 1 if edge == "first" else days, year=2024 if days == 29 else 2026
    )
    context, page, chart = open_chart(
        browser, chart_server, width=width, view=view, data=data
    )
    try:
        g = assert_geometry(chart, data)
        name = f"{view}-{width}-{days}-{edge}"
        (artifacts / f"{name}.json").write_text(json.dumps(g, indent=2))
        chart.screenshot(path=str(artifacts / f"{name}.png"))
        if days in (7, 31) and edge == "last":
            page.screenshot(path=str(artifacts / f"{name}-page.png"), full_page=True)
        expect(chart).to_contain_text("This week" if days == 7 else "This month")
        expect(chart).to_contain_text("3-week avg" if days == 7 else "3-month avg")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("year,days", [(2026, 365), (2024, 366)])
@pytest.mark.parametrize("edge", ["first", "last"])
def test_ytd_calendar_axis(browser, chart_server, artifacts, width, year, days, edge):
    data = trend(days, 1 if edge == "first" else days, year=year)
    context, page, chart = open_chart(
        browser, chart_server, width=width, view="insights", data=data
    )
    try:
        g = assert_geometry(chart, data)
        name = f"ytd-{width}-{year}-{edge}"
        (artifacts / f"{name}.json").write_text(json.dumps(g, indent=2))
        chart.screenshot(path=str(artifacts / f"{name}.png"))
        expect(chart).to_contain_text("Year to date")
        expect(chart).not_to_contain_text("avg")
        svg = chart.locator("svg.recharts-surface").bounding_box()
        page.mouse.move(svg["x"] + g["markerX"], svg["y"] + 90)
        tooltip = chart.locator(".recharts-tooltip-wrapper")
        expect(tooltip).to_contain_text("Jan 01" if edge == "first" else "Dec 31")
        expect(tooltip).to_contain_text("Current:")
        expect(tooltip).not_to_contain_text("Average:")
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("view", ["home", "insights"])
@pytest.mark.parametrize(
    "period,days",
    [
        ("last_week", 7),
        ("last_month", 31),
        ("future_month", 28),
    ],
)
def test_noncurrent_windows_no_marker(browser, chart_server, width, view, period, days):
    data = trend(days, None)
    context, _, chart = open_chart(
        browser,
        chart_server,
        width=width,
        view=view,
        data=data,
        period="this_month" if period == "future_month" else period,
    )
    try:
        g = assert_geometry(chart, data)
        assert abs(g["areaEnd"] - g["averageEnd"]) < 0.5
        if view == "insights" and period != "future_month":
            expect(chart).to_contain_text(
                "Last week" if period == "last_week" else "Last month"
            )
    finally:
        context.close()


@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("view", ["home", "insights"])
@pytest.mark.parametrize("amount", [0, 9876543.21])
def test_amounts_and_tooltip_values(
    browser, chart_server, artifacts, width, view, amount
):
    data = trend(31, 16, amount=amount)
    context, page, chart = open_chart(
        browser, chart_server, width=width, view=view, data=data
    )
    try:
        g = assert_geometry(chart, data)
        svg = chart.locator("svg.recharts-surface").bounding_box()
        page.mouse.move(svg["x"] + g["markerX"], svg["y"] + 90)
        tooltip = chart.locator(".recharts-tooltip-wrapper")
        expect(tooltip).to_contain_text("Day 16")
        formatted = page.evaluate(
            "v => new Intl.NumberFormat('en-US', {style:'currency',currency:'EUR'}).format(v)",
            16 * amount,
        )
        expect(tooltip).to_contain_text(f"Current: {formatted}")
        average = page.evaluate(
            "v => new Intl.NumberFormat('en-US', {style:'currency',currency:'EUR'}).format(v)",
            32 * amount,
        )
        expect(tooltip).to_contain_text(f"Average: {average}")
        chart.screenshot(path=str(artifacts / f"amount-{view}-{width}-{amount}.png"))
        # No current value is fabricated beyond today, but comparison remains.
        page.mouse.move(svg["x"] + g["averageEnd"], svg["y"] + 90)
        expect(tooltip).to_contain_text("Day 31")
        expect(tooltip).not_to_contain_text("Current:")
        expect(tooltip).to_contain_text("Average:")
    finally:
        context.close()


@pytest.mark.parametrize("count", [0, 1, 4, 8, 9, None])
def test_weekly_legend_metadata(browser, chart_server, count):
    data = trend(7, 4, count=count if count is not None else 3)
    if count is None:
        del data["average_period_count"]
    context, _, chart = open_chart(
        browser, chart_server, width=390, view="home", data=data
    )
    try:
        if count == 0:
            expect(chart).not_to_contain_text("avg")
            expect(chart.locator(".recharts-line-curve")).to_have_count(0)
        else:
            expect(chart).to_contain_text(
                "Weekly avg" if count is None else f"{count}-week avg"
            )
    finally:
        context.close()


def test_axis_helper_selected_span_and_resize(browser, chart_server):
    context = browser.new_context()
    page = context.new_page()
    page.goto(chart_server)
    result = page.evaluate(
        """async () => {
      const {getTrendDomain, getTrendTicks} = await import('/src/lib/spendingTrendAxis.ts');
      const data = {current_series:[{day:10},{day:100}], average_series:[{day:365}],
                    current_day:10};
      const domain = getTrendDomain(data);
      return {domain,
        narrow:getTrendTicks(domain,200,'quarterly',2026),
        wide:getTrendTicks(domain,800,'quarterly',2026),
        empty:getTrendDomain({current_series:[]}),
        single:getTrendDomain({current_series:[{day:12}]})};
    }"""
    )
    try:
        assert result["domain"] == [10, 100]
        assert result["empty"] == [1, 2]
        assert result["single"] == [11.5, 12.5]
        assert len(result["wide"]) > len(result["narrow"])
        for key in ["narrow", "wide"]:
            ticks = result[key]
            assert ticks[0] == 10 and ticks[-1] <= 100
            assert len(set(b - a for a, b in zip(ticks, ticks[1:]))) == 1
    finally:
        context.close()


def test_live_resize_recomputes_ticks(browser, chart_server):
    data = trend(31, 31)
    context, page, chart = open_chart(
        browser, chart_server, width=390, view="home", data=data
    )
    try:
        narrow = assert_geometry(chart, data)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.wait_for_timeout(1700)
        wide = assert_geometry(chart, data)
        assert len(wide["ticks"]) > len(narrow["ticks"])
        page.set_viewport_size({"width": 390, "height": 1000})
        page.wait_for_timeout(1700)
        assert len(assert_geometry(chart, data)["ticks"]) == len(narrow["ticks"])
    finally:
        context.close()


def test_issue65_original_label_position_reproduces_clip(
    browser, chart_server, artifacts
):
    data = trend(31, 16)
    context, _, chart = open_chart(
        browser, chart_server, width=390, view="home", data=data, baseline=True
    )
    try:
        g = geometry(chart)
        assert g["label"]["y"] < 0, g
        with pytest.raises(AssertionError):
            assert_geometry(chart, data)
        (artifacts / "issue65-original-top-label.json").write_text(
            json.dumps(g, indent=2)
        )
        chart.screenshot(path=str(artifacts / "issue65-original-top-label.png"))
    finally:
        context.close()
