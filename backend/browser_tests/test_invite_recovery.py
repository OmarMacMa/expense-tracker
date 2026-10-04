import json
import re
from datetime import UTC, datetime, timedelta

import pytest
from playwright.async_api import expect
from sqlalchemy import select

from app.models import Expense, InviteLink, Space, SpaceMember
from app.services.membership_transition import leave_space
from browser_tests.conftest import authenticate


async def invitation(real_db, *, source=True):
    actor, host = await real_db.user("Original Owner"), await real_db.user("Host")
    origin = await real_db.space(actor, "Source Family") if source else None
    destination = await real_db.space(host, "Destination Family")
    invite = await real_db.invite(destination, host)
    return actor, host, origin, destination, invite


async def open_confirmation(page, source_name="Source Family"):
    await page.get_by_role("button", name="Review leaving space").click()
    dialog = page.get_by_role("dialog")
    await expect(
        dialog.get_by_label(f'Type "{source_name}" exactly to confirm')
    ).to_be_visible()
    return dialog


async def spa_navigate(page, path):
    await page.evaluate(
        "(path) => { history.pushState({}, '', path); "
        "window.dispatchEvent(new PopStateEvent('popstate')); }",
        path,
    )


@pytest.mark.parametrize("width", [390, 1440])
async def test_real_atomic_recovery_exact_confirmation_and_cache(
    real_db, context, tmp_path, width
):
    actor, _, source, destination, invite = await invitation(real_db)
    history = await real_db.populate(source, actor)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.set_viewport_size({"width": width, "height": 844})
    await context.add_init_script(
        "localStorage.setItem('expense-tracker:period', 'this_week')"
    )
    historical_id = history["expense"]
    await page.goto(f"/transactions/{historical_id}")
    # Populate the real expense detail cache before switching, without a reload.
    await expect(page.get_by_text("History", exact=True)).to_be_visible()
    await spa_navigate(page, "/home")
    await page.wait_for_load_state("networkidle")
    await spa_navigate(page, f"/join/{invite.token}")
    await expect(
        page.get_by_role("link", name="Review switch in Settings")
    ).to_be_visible()
    # Inspect real rendered DOM, then act through the actual router link.
    assert "Review switch in Settings" in await page.locator("body").inner_text()
    await page.get_by_role("link", name="Review switch in Settings").click()
    dialog = await open_confirmation(page)
    await expect(
        dialog.get_by_role("button", name="Cancel", exact=True)
    ).to_be_focused()
    submit = dialog.get_by_role(
        "button", name="Leave and join Destination Family", exact=True
    )
    await expect(submit).to_be_disabled()
    await dialog.get_by_label('Type "Source Family" exactly to confirm').fill(
        "source family"
    )
    await expect(submit).to_be_disabled()
    await expect(dialog).to_contain_text("permanently deletes")
    await expect(dialog).to_contain_text("No data is transferred")
    await page.screenshot(
        path=str(tmp_path / f"confirmation-{width}.png"), full_page=True
    )
    assert await page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    )
    await dialog.get_by_label('Type "Source Family" exactly to confirm').fill(
        "Source Family"
    )
    await submit.click()
    await expect(page).to_have_url(re.compile(r"/home$"))
    await expect(page.get_by_text("The space was deleted", exact=True)).to_be_visible()
    await page.wait_for_load_state("networkidle")
    assert "Source Family" not in await page.locator("body").inner_text()
    assert (
        await page.evaluate("localStorage.getItem('expense-tracker:period')")
        == "this_week"
    )
    assert await page.evaluate("sessionStorage.getItem('pending_invite_token')") is None
    await spa_navigate(page, f"/transactions/{historical_id}")
    await expect(page.get_by_text("Expense not found.", exact=True)).to_be_visible(
        timeout=15000
    )
    assert "History" not in await page.locator("body").inner_text()
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id) is None
        assert (
            await db.scalar(
                select(SpaceMember.space_id).where(SpaceMember.user_id == actor.id)
            )
            == destination.id
        )
        assert (await db.get(InviteLink, invite.id)).used_by == actor.id


async def test_signed_in_join_refreshes_auth_before_home(real_db, context):
    actor, _, _, destination, invite = await invitation(real_db, source=False)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await page.get_by_role("button", name='Yes, join "Destination Family"').click()
    await expect(page).to_have_url(re.compile(r"/home$"))
    assert "onboarding" not in page.url
    async with real_db.sessions() as db:
        assert (
            await db.scalar(
                select(SpaceMember.space_id).where(SpaceMember.user_id == actor.id)
            )
            == destination.id
        )


async def test_oauth_boundary_retry_retains_invite(real_db, context):
    actor, _, _, _, invite = await invitation(real_db, source=False)
    attempts = 0

    async def oauth_boundary(route):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            await route.fulfill(
                status=302, headers={"location": "/?error=oauth_failed"}
            )
        else:
            await authenticate(context, actor)
            await route.fulfill(status=302, headers={"location": "/auth/callback"})

    await context.route("**/api/v1/auth/google", oauth_boundary)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await page.get_by_role("button", name="Sign in with Google", exact=True).click()
    await expect(page.get_by_role("alert")).to_contain_text("Sign-in failed")
    assert invite.token in await page.evaluate(
        "sessionStorage.getItem('pending_invite_token')"
    )
    await page.get_by_role("button", name="Sign in with Google", exact=True).click()
    await expect(page).to_have_url(re.compile(f"/join/{invite.token}$"))
    await page.get_by_role("button", name='Yes, join "Destination Family"').click()
    await expect(page).to_have_url(re.compile(r"/home$"))


async def test_already_target_cancel_and_token_replacement(real_db, context):
    actor, host, source, destination, invite = await invitation(real_db)
    await authenticate(context, host)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await expect(
        page.get_by_text('You\'re already in "Destination Family".')
    ).to_be_visible()
    await expect(
        page.get_by_role("link", name="Review switch in Settings")
    ).to_have_count(0)
    await page.get_by_role("button", name="Cancel invitation").click()
    assert await page.evaluate("sessionStorage.getItem('pending_invite_token')") is None
    await authenticate(context, actor)
    await page.goto(f"/join/{invite.token}")
    new_invite = await real_db.invite(destination, host)
    await page.goto(f"/join/{new_invite.token}")
    stored = json.loads(
        await page.evaluate("sessionStorage.getItem('pending_invite_token')")
    )
    assert stored["token"] == new_invite.token
    await page.get_by_role("button", name="Cancel invitation").click()
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)
        assert (await db.get(InviteLink, new_invite.id)).used_at is None


@pytest.mark.parametrize(
    "state", ["expired", "used", "full", "invalid", "network", "unknown-error"]
)
async def test_visible_preview_errors_and_cancel(real_db, context, state):
    actor, host, source, destination, invite = await invitation(real_db)
    token = invite.token
    async with real_db.sessions() as db:
        row = await db.get(InviteLink, invite.id)
        if state == "expired":
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        if state == "used":
            row.used_at, row.used_by = datetime.now(UTC), host.id
        await db.commit()
    if state == "full":
        for _ in range(9):
            await real_db.member(destination, await real_db.user())
    if state == "invalid":
        token = "missing-invite"
    if state in ("network", "unknown-error"):

        async def fail(route):
            if state == "network":
                await route.abort()
            else:
                await route.fulfill(status=500, json={"detail": "unknown"})

        await context.route("**/spaces/invites/*/preview", fail)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto(f"/join/{token}")
    await expect(page.get_by_role("alert")).to_be_visible()
    await expect(
        page.get_by_role("link", name="Review switch in Settings")
    ).to_have_count(0)
    await page.get_by_role("button", name="Cancel invitation").click()
    await expect(page).to_have_url(re.compile(r"/home$"))
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)


@pytest.mark.parametrize("change", ["expiry", "replacement", "invalid"])
async def test_pending_change_never_becomes_standalone_deletion(
    real_db, context, change
):
    actor, _, source, _, invite = await invitation(real_db)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await page.get_by_role("link", name="Review switch in Settings").click()
    dialog = await open_confirmation(page)
    await dialog.get_by_label('Type "Source Family" exactly to confirm').fill(
        "Source Family"
    )
    value = {
        "token": "replaced" if change == "replacement" else invite.token,
        "ts": 0 if change == "expiry" else datetime.now(UTC).timestamp() * 1000,
    }
    await page.evaluate(
        "(value) => sessionStorage.setItem('pending_invite_token', value)",
        "broken" if change == "invalid" else json.dumps(value),
    )
    await expect(dialog.get_by_role("alert")).to_contain_text("changed or expired")
    await expect(
        dialog.get_by_role(
            "button", name="Leave and join Destination Family", exact=True
        )
    ).to_be_disabled()
    await dialog.get_by_role("button", name="Cancel", exact=True).click()
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)


async def test_failed_real_transfer_keeps_source_and_invite(real_db, context):
    actor, _, source, _, invite = await invitation(real_db)
    await real_db.populate(source, actor)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await page.get_by_role("link", name="Review switch in Settings").click()
    dialog = await open_confirmation(page)
    async with real_db.sessions() as db:
        (await db.get(InviteLink, invite.id)).expires_at = datetime.now(
            UTC
        ) - timedelta(seconds=1)
        await db.commit()
    await dialog.get_by_label('Type "Source Family" exactly to confirm').fill(
        "Source Family"
    )
    await dialog.get_by_role(
        "button", name="Leave and join Destination Family", exact=True
    ).click()
    await expect(dialog.get_by_role("alert")).to_contain_text("expired")
    await expect(page.get_by_text("The space was deleted", exact=True)).to_have_count(0)
    await expect(page.get_by_text("You've left the space", exact=True)).to_have_count(0)
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)
        assert (await db.get(InviteLink, invite.id)).used_at is None
        assert await db.scalar(select(Expense.id).where(Expense.space_id == source.id))


async def test_postcommit_refresh_failure_only_retries_refresh(real_db, context):
    actor, _, source, _, invite = await invitation(real_db)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await page.get_by_role("link", name="Review switch in Settings").click()
    dialog = await open_confirmation(page)
    mutations = 0

    async def count_transfer(route):
        nonlocal mutations
        mutations += 1
        await route.continue_()

    await context.route("**/membership-transfers", count_transfer)
    await context.route(
        "**/api/v1/auth/me",
        lambda route: route.fulfill(
            status=503, json={"error": {"message": "Refresh unavailable"}}
        ),
    )
    await dialog.get_by_label('Type "Source Family" exactly to confirm').fill(
        "Source Family"
    )
    await dialog.get_by_role(
        "button", name="Leave and join Destination Family", exact=True
    ).click()
    await expect(
        page.get_by_role("heading", name="Membership change completed")
    ).to_be_visible()
    await expect(page.get_by_role("button", name="Refresh session")).to_be_visible()
    await expect(page.get_by_text("The space was deleted", exact=True)).to_have_count(1)
    assert mutations == 1
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id) is None
    await context.unroute("**/api/v1/auth/me")
    await page.get_by_role("button", name="Refresh session").click()
    await expect(page).to_have_url(re.compile(r"/home$"))
    assert mutations == 1
    await expect(page.get_by_text("The space was deleted", exact=True)).to_have_count(1)


async def test_standalone_leave_and_expired_intent_guard(real_db, context):
    actor = await real_db.user()
    source = await real_db.space(actor, "Source Family")
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto("/settings")
    await page.evaluate(
        "sessionStorage.setItem('pending_invite_token', "
        "JSON.stringify({token:'old',ts:0}))"
    )
    dialog = await open_confirmation(page)
    await expect(dialog.get_by_role("alert")).to_contain_text("expired")
    await expect(
        dialog.get_by_role("button", name="Leave space", exact=True)
    ).to_be_disabled()
    await dialog.get_by_role(
        "button", name="Abandon invitation (no membership change)"
    ).click()
    dialog = await open_confirmation(page)
    await dialog.get_by_label('Type "Source Family" exactly to confirm').fill(
        "Source Family"
    )
    await dialog.get_by_role("button", name="Leave space", exact=True).click()
    await expect(page).to_have_url(re.compile(r"/onboarding$"))
    await expect(page.get_by_text("The space was deleted", exact=True)).to_be_visible()
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id) is None


async def test_shared_space_leave_success_notification(real_db, context):
    actor, survivor = await real_db.user(), await real_db.user()
    source = await real_db.space(actor, "Source Family")
    await real_db.member(source, survivor)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto("/settings")
    dialog = await open_confirmation(page)
    await dialog.get_by_label('Type "Source Family" exactly to confirm').fill(
        "Source Family"
    )
    await dialog.get_by_role("button", name="Leave space", exact=True).click()
    await expect(page).to_have_url(re.compile(r"/onboarding$"))
    await expect(page.get_by_text("You've left the space", exact=True)).to_be_visible()
    await expect(page.get_by_text("The space was deleted", exact=True)).to_have_count(0)
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)
        assert list(
            await db.scalars(
                select(SpaceMember.user_id).where(SpaceMember.space_id == source.id)
            )
        ) == [survivor.id]


async def test_survivor_history_edit_and_method_management(real_db, context):
    actor, survivor = await real_db.user("Original Owner"), await real_db.user(
        "Survivor"
    )
    source = await real_db.space(actor, "Source Family")
    await real_db.member(source, survivor)
    ids = await real_db.populate(source, actor)
    confirmation = await real_db.confirmation(source, actor)
    async with real_db.sessions() as db:
        await leave_space(db, source.id, actor.id, confirmation)
    await authenticate(context, survivor)
    page = await context.new_page()
    await page.goto(f"/transactions/{ids['expense']}")
    await page.wait_for_load_state("networkidle")
    assert "Original Owner" in await page.locator("body").inner_text()
    buttons = await page.get_by_role("button").all_text_contents()
    assert any("Edit" in text for text in buttons), buttons
    await page.get_by_role("button", name="Edit", exact=True).click()
    await expect(page.get_by_text("Original Owner", exact=True)).to_be_visible()
    await page.get_by_role("button", name="Save Changes").click()
    await expect(page.get_by_text("Expense updated")).to_be_visible()
    await page.goto("/settings/payment-methods")
    await expect(page.get_by_text("Original Owner (former member)")).to_be_visible()
    await page.get_by_role("button", name="Delete Old card").click()
    await page.get_by_role("button", name="Delete", exact=True).click()
    await expect(page.get_by_text("Payment method deleted")).to_be_visible()
    await page.goto(f"/transactions/{ids['expense']}")
    await expect(page.get_by_text("Deleted method", exact=True)).to_be_visible()


async def test_preview_cancel_aborts_stale_response(real_db, context):
    actor, _, source, _, invite = await invitation(real_db)
    await authenticate(context, actor)
    import asyncio

    requested = asyncio.Event()
    release = asyncio.Event()

    async def delayed_preview(route):
        requested.set()
        await release.wait()
        await route.continue_()

    await context.route("**/spaces/invites/*/preview", delayed_preview)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}", wait_until="domcontentloaded")
    await requested.wait()
    await page.get_by_role("button", name="Cancel invitation").click()
    release.set()
    await expect(page).to_have_url(re.compile(r"/home$"))
    await page.wait_for_load_state("networkidle")
    assert await page.evaluate("sessionStorage.getItem('pending_invite_token')") is None
    assert "Join a Space" not in await page.locator("body").inner_text()
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)
        assert (await db.get(InviteLink, invite.id)).used_at is None


async def test_network_join_failure_is_visible_without_optional_code(real_db, context):
    actor, _, _, _, invite = await invitation(real_db, source=False)
    await authenticate(context, actor)
    await context.route("**/spaces/join/*", lambda route: route.abort())
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await page.get_by_role("button", name='Yes, join "Destination Family"').click()
    await expect(page.get_by_role("alert")).to_be_visible()
    await expect(
        page.get_by_role("button", name='Yes, join "Destination Family"')
    ).to_be_enabled()
    async with real_db.sessions() as db:
        assert (await db.get(InviteLink, invite.id)).used_at is None
        assert not await db.scalar(
            select(SpaceMember.id).where(SpaceMember.user_id == actor.id)
        )


async def test_changed_counts_refresh_requires_new_confirmation(real_db, context):
    actor, _, source, _, invite = await invitation(real_db)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await page.get_by_role("link", name="Review switch in Settings").click()
    dialog = await open_confirmation(page)
    field = dialog.get_by_label('Type "Source Family" exactly to confirm')
    await field.fill("Source Family")
    await real_db.populate(source, actor)
    await dialog.get_by_role(
        "button", name="Leave and join Destination Family", exact=True
    ).click()
    await expect(dialog.get_by_role("alert")).to_contain_text("changed")
    await expect(field).to_have_value("")
    await expect(
        dialog.get_by_role(
            "button", name="Leave and join Destination Family", exact=True
        )
    ).to_be_disabled()
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)
        assert (await db.get(InviteLink, invite.id)).used_at is None


async def test_expired_session_reauthentication_retains_intended_target(
    real_db, context
):
    actor, _, source, _, invite = await invitation(real_db)
    await authenticate(context, actor)
    page = await context.new_page()
    await page.goto(f"/join/{invite.token}")
    await page.get_by_role("link", name="Review switch in Settings").click()
    dialog = await open_confirmation(page)
    await context.clear_cookies()
    await dialog.get_by_label('Type "Source Family" exactly to confirm').fill(
        "Source Family"
    )
    await dialog.get_by_role(
        "button", name="Leave and join Destination Family", exact=True
    ).click()
    await expect(dialog.get_by_role("alert")).to_be_visible()

    async def oauth_boundary(route):
        await authenticate(context, actor)
        await route.fulfill(status=302, headers={"location": "/auth/callback"})

    await context.route("**/api/v1/auth/google", oauth_boundary)
    await dialog.get_by_role("button", name="Sign in again").click()
    await expect(page).to_have_url(re.compile(f"/join/{invite.token}$"))
    await expect(
        page.get_by_role("link", name="Review switch in Settings")
    ).to_be_visible()
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)
        assert (await db.get(InviteLink, invite.id)).used_at is None
