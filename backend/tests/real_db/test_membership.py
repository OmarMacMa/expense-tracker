import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, event, func, select, text

from app.auth.jwt import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import (
    Expense,
    ExpenseLine,
    InviteLink,
    LimitFilter,
    PaymentMethod,
    Space,
    SpaceMember,
    Tag,
    User,
)
from app.models.expense import expense_line_tags
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.payment_method import PaymentMethodUpdate
from app.schemas.space import MembershipTransfer, SpaceCreate
from app.services.expense import build_expense_response, create_expense, update_expense
from app.services.invite import join_space
from app.services.membership import SPACE_DATA, leave_preview
from app.services.membership_transition import leave_space, transfer_membership
from app.services.payment_method import (
    delete_payment_method,
    payment_method_response,
    update_payment_method,
)
from app.services.space import create_space
from tests.membership_support import MembershipDatabase, run_operation


async def setup_transfer(real_db: MembershipDatabase):
    actor, host = await real_db.user("Former Owner"), await real_db.user("Host")
    source = await real_db.space(actor)
    destination = await real_db.space(host, "Destination")
    invite = await real_db.invite(destination, host)
    confirmation = await real_db.confirmation(source, actor)
    data = MembershipTransfer(**confirmation.model_dump(), invite_token=invite.token)
    return actor, host, source, destination, invite, data


async def test_populated_atomic_transfer_and_control_preservation(real_db):
    actor, host, source, destination, invite, _ = await setup_transfer(real_db)
    await real_db.populate(source, actor)
    control = await real_db.space(await real_db.user(), "Control")
    await real_db.populate(control, await real_db.user("Attribution"))
    confirmation = await real_db.confirmation(source, actor)
    async with real_db.sessions() as db:
        control_member = await db.scalar(
            select(SpaceMember.user_id).where(SpaceMember.space_id == control.id)
        )
        before_control = await leave_preview(db, control.id, control_member)
        assert all(value > 0 for value in confirmation.preview.counts.values())
        outcome = await transfer_membership(
            db,
            source.id,
            actor.id,
            MembershipTransfer(
                **confirmation.model_dump(),
                invite_token=invite.token,
            ),
        )
        assert outcome.source_deleted
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id) is None
        assert await db.get(User, actor.id)
        assert (await db.get(InviteLink, invite.id)).used_by == actor.id
        for model in SPACE_DATA:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.space_id == source.id)
                )
                == 0
            )
        for model in (ExpenseLine, LimitFilter, expense_line_tags):
            # The populated control remains; only its children exist.
            assert await db.scalar(select(func.count()).select_from(model)) > 0
        assert await leave_preview(db, control.id, control_member) == before_control
        assert (
            await db.scalar(
                select(SpaceMember.space_id).where(SpaceMember.user_id == actor.id)
            )
            == destination.id
        )


@pytest.mark.parametrize(
    "failure",
    [
        "expired",
        "used",
        "unknown",
        "full",
        "same",
        "name",
        "changed",
        "legacy",
        "deleted",
        "counts",
        "members",
    ],
)
async def test_failed_recovery_preserves_source(real_db, failure):
    actor, host, source, destination, invite, _ = await setup_transfer(real_db)
    await real_db.populate(source, actor)
    confirmation = await real_db.confirmation(source, actor)
    data = MembershipTransfer(**confirmation.model_dump(), invite_token=invite.token)
    async with real_db.sessions() as db:
        row = await db.get(InviteLink, invite.id)
        if failure == "expired":
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif failure == "used":
            row.used_at, row.used_by = datetime.now(UTC), host.id
        elif failure == "unknown":
            data.invite_token = uuid.uuid4().hex
        elif failure == "same":
            row.space_id = source.id
        elif failure == "name":
            data.source_name = "wrong"
        elif failure == "changed":
            (await db.get(Space, source.id)).name = "Renamed"
        elif failure == "counts":
            db.add(Tag(space_id=source.id, name="changed-count"))
        elif failure == "members":
            db.add(SpaceMember(space_id=source.id, user_id=host.id))
        elif failure == "legacy":
            db.add(SpaceMember(space_id=destination.id, user_id=actor.id))
        elif failure == "deleted":
            await db.execute(
                delete(InviteLink).where(InviteLink.space_id == destination.id)
            )
            await db.execute(
                delete(PaymentMethod).where(PaymentMethod.space_id == destination.id)
            )
            from app.models import Category

            await db.execute(
                delete(Category).where(Category.space_id == destination.id)
            )
            await db.execute(
                delete(SpaceMember).where(SpaceMember.space_id == destination.id)
            )
            await db.execute(delete(Space).where(Space.id == destination.id))
        await db.commit()
    if failure == "full":
        for _ in range(9):
            await real_db.member(destination, await real_db.user())
    async with real_db.sessions() as db:
        before = await leave_preview(db, source.id, actor.id)
        used_before = (
            (await db.get(InviteLink, invite.id)).used_at
            if failure != "deleted"
            else None
        )
        with pytest.raises(HTTPException):
            await transfer_membership(db, source.id, actor.id, data)
    async with real_db.sessions() as db:
        assert await leave_preview(db, source.id, actor.id) == before
        if failure != "deleted":
            assert (await db.get(InviteLink, invite.id)).used_at == used_before


async def test_forced_precommit_failure_rolls_back_all_tables(real_db, monkeypatch):
    actor, host, source, destination, invite, _ = await setup_transfer(real_db)
    await real_db.populate(source, actor)
    confirmation = await real_db.confirmation(source, actor)
    async with real_db.sessions() as db:
        before = await leave_preview(db, source.id, actor.id)

        async def fail_commit():
            await db.flush()
            # Demonstrate the mutation really happened inside this transaction.
            assert await db.get(Space, source.id) is None
            assert await db.scalar(
                select(SpaceMember.id).where(
                    SpaceMember.space_id == destination.id,
                    SpaceMember.user_id == actor.id,
                )
            )
            raise RuntimeError("Injected failure before durable commit")

        monkeypatch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="Injected"):
            await transfer_membership(
                db,
                source.id,
                actor.id,
                MembershipTransfer(
                    **confirmation.model_dump(),
                    invite_token=invite.token,
                ),
            )
    async with real_db.sessions() as db:
        assert await leave_preview(db, source.id, actor.id) == before
        assert (await db.get(InviteLink, invite.id)).used_at is None
        assert not await db.scalar(
            select(SpaceMember.id).where(
                SpaceMember.space_id == destination.id, SpaceMember.user_id == actor.id
            )
        )


async def test_shared_history_survivor_permissions_and_spender(real_db):
    actor, survivor, outsider = (
        await real_db.user("Original"),
        await real_db.user(),
        await real_db.user(),
    )
    space = await real_db.space(actor)
    await real_db.member(space, survivor)
    ids = await real_db.populate(space, actor)
    async with real_db.sessions() as db:
        with pytest.raises(HTTPException) as denied:
            await delete_payment_method(db, space.id, ids["method"], survivor.id)
        assert denied.value.status_code == 403
        await db.rollback()
    confirmation = await real_db.confirmation(space, actor)
    async with real_db.sessions() as db:
        outcome = await leave_space(db, space.id, actor.id, confirmation)
        assert not outcome.source_deleted
    async with real_db.sessions() as db:
        pm = await db.get(PaymentMethod, ids["method"])
        metadata = await payment_method_response(db, pm, survivor.id)
        assert metadata["owner_display_name"] == "Original"
        assert metadata["can_manage"] and not metadata["owner_is_member"]
        assert not (await payment_method_response(db, pm, actor.id))["can_manage"]
        expense = await update_expense(
            db,
            space.id,
            ids["expense"],
            ExpenseUpdate(spender_id=actor.id, notes="Edited"),
        )
        assert (await build_expense_response(db, expense))["spender"][
            "display_name"
        ] == "Original"
        with pytest.raises(HTTPException):
            await update_expense(
                db, space.id, ids["expense"], ExpenseUpdate(spender_id=outsider.id)
            )
        await db.rollback()
        await update_payment_method(
            db,
            space.id,
            ids["method"],
            survivor.id,
            PaymentMethodUpdate(label="Survivor card"),
        )
        cash = await db.scalar(
            select(PaymentMethod).where(
                PaymentMethod.space_id == space.id, PaymentMethod.is_system.is_(True)
            )
        )
        with pytest.raises(HTTPException):
            await delete_payment_method(db, space.id, cash.id, survivor.id)
        await db.rollback()
        with pytest.raises(HTTPException):
            await delete_payment_method(db, space.id, ids["method"], actor.id)
        await db.rollback()
        await delete_payment_method(db, space.id, ids["method"], survivor.id)
    async with real_db.sessions() as db:
        assert (await db.get(Expense, ids["expense"])).payment_method_id is None


async def test_api_preview_confirmation_cookie_and_old_jwt(real_db):
    actor = await real_db.user()
    source = await real_db.space(actor)
    stranger = await real_db.user()

    async def dependency():
        async with real_db.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            url = f"/api/v1/spaces/{source.id}"
            assert (await client.get(f"{url}/leave-preview")).status_code == 401
            client.cookies.set("access_token", create_access_token(stranger.id))
            for method, path, body in [
                ("GET", "/leave-preview", None),
                (
                    "DELETE",
                    "/members/me",
                    (await real_db.confirmation(source, actor)).model_dump(mode="json"),
                ),
                (
                    "POST",
                    "/membership-transfers",
                    {
                        **(await real_db.confirmation(source, actor)).model_dump(
                            mode="json"
                        ),
                        "invite_token": "unknown",
                    },
                ),
            ]:
                assert (
                    await client.request(method, url + path, json=body)
                ).status_code == 404
            old_token = create_access_token(actor.id)
            client.cookies.set("access_token", old_token)
            preview = (await client.get(f"{url}/leave-preview")).json()
            wrong = await client.request(
                "DELETE",
                f"{url}/members/me",
                json={"source_name": "wrong", "preview": preview},
            )
            assert wrong.status_code == 422
            response = await client.request(
                "DELETE",
                f"{url}/members/me",
                json={"source_name": source.name, "preview": preview},
            )
            assert response.status_code == 200
            assert "HttpOnly" in response.headers["set-cookie"]
            assert "SameSite=lax" in response.headers["set-cookie"]
            client.cookies.clear()
            client.cookies.set("access_token", old_token)
            assert (await client.get(f"{url}/expenses")).status_code == 403
            assert (await client.get("/api/v1/auth/me")).json()["spaces"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)


async def race(real_db, *operations):
    results = await asyncio.wait_for(
        asyncio.gather(
            *(run_operation(real_db, operation) for operation in operations)
        ),
        timeout=15,
    )
    assert all(
        not isinstance(result, Exception) or isinstance(result, HTTPException)
        for result in results
    ), results
    return results


async def test_create_vs_join_and_two_joins(real_db):
    host, actor = await real_db.user(), await real_db.user()
    destination = await real_db.space(host, "Destination")
    invite = await real_db.invite(destination, host)
    results = await race(
        real_db,
        lambda db: create_space(
            db, actor, SpaceCreate(name="New", currency_code="USD", timezone="UTC")
        ),
        lambda db: join_space(db, invite.token, actor.id),
    )
    for result in results:
        if isinstance(result, Space):
            real_db.space_ids.append(result.id)
    assert sum(not isinstance(result, Exception) for result in results) == 1
    other = await real_db.user()
    invite2 = await real_db.invite(destination, host)
    results = await race(
        real_db,
        lambda db: join_space(db, invite2.token, other.id),
        lambda db: join_space(db, invite2.token, other.id),
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    async with real_db.sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(SpaceMember)
                .where(SpaceMember.user_id == actor.id)
            )
            == 1
        )


async def test_same_invite_refreshes_stale_identity_map(real_db):
    host, first, second = (
        await real_db.user(),
        await real_db.user(),
        await real_db.user(),
    )
    destination = await real_db.space(host)
    invite = await real_db.invite(destination, host)
    async with real_db.sessions() as winner, real_db.sessions() as loser:
        stale = await loser.get(InviteLink, invite.id)
        assert stale.used_at is None
        await join_space(winner, invite.token, first.id)
        with pytest.raises(HTTPException) as used:
            await join_space(loser, invite.token, second.id)
        assert used.value.detail["error"]["code"] == "INVITE_USED"
        await loser.rollback()
    another = await real_db.invite(destination, host)
    third, fourth = await real_db.user(), await real_db.user()
    results = await race(
        real_db,
        lambda db: join_space(db, another.token, third.id),
        lambda db: join_space(db, another.token, fourth.id),
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1


async def test_last_slot_contention(real_db):
    host = await real_db.user()
    destination = await real_db.space(host)
    for _ in range(8):
        await real_db.member(destination, await real_db.user())
    first, second = await real_db.user(), await real_db.user()
    invites = [await real_db.invite(destination, host) for _ in range(2)]
    results = await race(
        real_db,
        lambda db: join_space(db, invites[0].token, first.id),
        lambda db: join_space(db, invites[1].token, second.id),
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    async with real_db.sessions() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(SpaceMember)
                .where(SpaceMember.space_id == destination.id)
            )
            == 10
        )


async def test_two_leaves_require_changed_preview_confirmation(real_db):
    first, second = await real_db.user(), await real_db.user()
    source = await real_db.space(first)
    await real_db.member(source, second)
    one, two = await real_db.confirmation(source, first), await real_db.confirmation(
        source, second
    )
    results = await race(
        real_db,
        lambda db: leave_space(db, source.id, first.id, one),
        lambda db: leave_space(db, source.id, second.id, two),
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    remaining = second if isinstance(results[0], Exception) is False else first
    fresh = await real_db.confirmation(source, remaining)
    async with real_db.sessions() as db:
        assert (await leave_space(db, source.id, remaining.id, fresh)).source_deleted


async def test_last_member_leave_vs_join(real_db):
    owner, joiner = await real_db.user(), await real_db.user()
    source = await real_db.space(owner)
    invite = await real_db.invite(source, owner)
    confirmation = await real_db.confirmation(source, owner)
    results = await race(
        real_db,
        lambda db: leave_space(db, source.id, owner.id, confirmation),
        lambda db: join_space(db, invite.token, joiner.id),
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    async with real_db.sessions() as db:
        space = await db.get(Space, source.id)
        if space:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(SpaceMember)
                    .where(SpaceMember.space_id == source.id)
                )
                == 2
            )


async def test_opposing_transfers_no_deadlock(real_db):
    first, second = await real_db.user(), await real_db.user()
    a, b = await real_db.space(first, "A"), await real_db.space(second, "B")
    # Keep both spaces alive regardless of which transfer wins first.
    await real_db.member(a, await real_db.user())
    await real_db.member(b, await real_db.user())
    ia, ib = await real_db.invite(a, first), await real_db.invite(b, second)
    ca, cb = await real_db.confirmation(a, first), await real_db.confirmation(b, second)
    results = await race(
        real_db,
        lambda db: transfer_membership(
            db,
            a.id,
            first.id,
            MembershipTransfer(**ca.model_dump(), invite_token=ib.token),
        ),
        lambda db: transfer_membership(
            db,
            b.id,
            second.id,
            MembershipTransfer(**cb.model_dump(), invite_token=ia.token),
        ),
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    # The losing preview changed because the winner joined its source.
    assert (
        next(result for result in results if isinstance(result, HTTPException)).detail[
            "error"
        ]["code"]
        == "PREVIEW_CHANGED"
    )


async def test_transfer_vs_standalone_leave(real_db):
    actor, _, source, destination, invite, data = await setup_transfer(real_db)
    confirmation = await real_db.confirmation(source, actor)
    results = await race(
        real_db,
        lambda db: transfer_membership(db, source.id, actor.id, data),
        lambda db: leave_space(db, source.id, actor.id, confirmation),
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id) is None
        memberships = list(
            await db.scalars(
                select(SpaceMember.space_id).where(SpaceMember.user_id == actor.id)
            )
        )
        consumed = (await db.get(InviteLink, invite.id)).used_at is not None
        assert memberships == ([destination.id] if consumed else [])


async def test_populated_standalone_leave_preserves_account(real_db):
    actor = await real_db.user()
    source = await real_db.space(actor)
    await real_db.populate(source, actor)
    confirmation = await real_db.confirmation(source, actor)
    async with real_db.sessions() as db:
        outcome = await leave_space(db, source.id, actor.id, confirmation)
        assert outcome.source_deleted and outcome.destination_space_id is None
    async with real_db.sessions() as db:
        assert await db.get(User, actor.id)
        assert await db.get(Space, source.id) is None
        for model in SPACE_DATA:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.space_id == source.id)
                )
                == 0
            )


async def test_leave_preview_default_rate_limit(real_db):
    actor = await real_db.user()
    source = await real_db.space(actor)

    async def dependency():
        async with real_db.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("access_token", create_access_token(actor.id))
            for _ in range(30):
                response = await client.get(f"/api/v1/spaces/{source.id}/leave-preview")
                assert response.status_code == 200
            limited = await client.get(f"/api/v1/spaces/{source.id}/leave-preview")
            assert limited.status_code == 429
            assert limited.json()["error"]["code"] == "RATE_LIMITED"
            assert int(limited.headers["retry-after"]) > 0
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_three_way_transfer_cycle_preserves_invariants(real_db):
    actors = [await real_db.user(f"Actor {number}") for number in range(3)]
    spaces = [
        await real_db.space(actor, f"Cycle {number}")
        for number, actor in enumerate(actors)
    ]
    for space in spaces:
        await real_db.member(space, await real_db.user("Survivor"))
    invites = [
        await real_db.invite(space, actor) for space, actor in zip(spaces, actors)
    ]
    confirmations = [
        await real_db.confirmation(space, actor) for space, actor in zip(spaces, actors)
    ]
    operations = []
    for number, actor in enumerate(actors):
        source = spaces[number]
        data = MembershipTransfer(
            **confirmations[number].model_dump(),
            invite_token=invites[(number + 1) % 3].token,
        )

        async def transfer(db, source=source, actor=actor, data=data):
            return await transfer_membership(db, source.id, actor.id, data)

        operations.append(transfer)
    results = await race(real_db, *operations)
    successes = sum(not isinstance(result, Exception) for result in results)
    assert 1 <= successes <= 2
    async with real_db.sessions() as db:
        for actor in actors:
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(SpaceMember)
                    .where(SpaceMember.user_id == actor.id)
                )
                == 1
            )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(InviteLink)
                .where(
                    InviteLink.id.in_([invite.id for invite in invites]),
                    InviteLink.used_at.is_not(None),
                )
            )
            == successes
        )
        for space in spaces:
            count = await db.scalar(
                select(func.count())
                .select_from(SpaceMember)
                .where(SpaceMember.space_id == space.id)
            )
            assert 1 <= count <= 3


@pytest.mark.parametrize("transfer", [False, True])
@pytest.mark.parametrize("shared_source", [False, True])
async def test_expense_insert_during_membership_change(
    real_db, monkeypatch, transfer, shared_source
):
    """FK checks must not deadlock against the transition's actor lock."""
    from app.services import membership_transition

    actor, _, source, destination, invite, _ = await setup_transfer(real_db)
    caller = actor
    if shared_source:
        caller = await real_db.user("Remaining member")
        await real_db.member(source, caller)
    confirmation = await real_db.confirmation(source, actor)
    async with real_db.sessions() as db:
        from app.models import Category

        category_id = await db.scalar(
            select(Category.id).where(Category.space_id == source.id)
        )

    actor_locked = asyncio.Event()
    continue_transition = asyncio.Event()
    expense_finished = asyncio.Event()
    expense_pid = asyncio.get_running_loop().create_future()
    original_lock_spaces = membership_transition.lock_spaces

    async def pause_before_space_lock(db, space_ids):
        actor_locked.set()
        await continue_transition.wait()
        return await original_lock_spaces(db, space_ids)

    monkeypatch.setattr(membership_transition, "lock_spaces", pause_before_space_lock)

    async def change_membership(db):
        if transfer:
            return await transfer_membership(
                db,
                source.id,
                actor.id,
                MembershipTransfer(
                    **confirmation.model_dump(), invite_token=invite.token
                ),
            )
        return await leave_space(db, source.id, actor.id, confirmation)

    async def save_expense(db):
        expense_pid.set_result(await db.scalar(text("SELECT pg_backend_pid()")))
        await actor_locked.wait()
        try:
            return await create_expense(
                db,
                source.id,
                ExpenseCreate(
                    merchant="Concurrent save",
                    purchase_datetime=datetime.now(UTC) - timedelta(seconds=1),
                    amount="10",
                    category_id=category_id,
                    spender_id=actor.id,
                ),
                caller.id,
            )
        finally:
            expense_finished.set()

    async def release_when_saved_or_blocked():
        pid = await expense_pid
        await actor_locked.wait()
        try:
            async with real_db.sessions() as db:
                for _ in range(150):
                    if expense_finished.is_set():
                        return
                    if await db.scalar(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": pid}
                    ):
                        # The old FOR UPDATE lock blocks the FK check here.
                        # Releasing the space lock then exposes the deadlock.
                        return
                    await asyncio.sleep(0.02)
            raise AssertionError("Expense did not finish or reach a lock wait")
        finally:
            continue_transition.set()

    results = await asyncio.wait_for(
        asyncio.gather(
            run_operation(real_db, change_membership),
            run_operation(real_db, save_expense),
            release_when_saved_or_blocked(),
        ),
        timeout=15,
    )
    transition_result, saved_expense, _ = results
    assert isinstance(saved_expense, Expense), results
    assert isinstance(transition_result, HTTPException), results
    assert transition_result.detail["error"]["code"] == "PREVIEW_CHANGED"
    async with real_db.sessions() as db:
        assert await db.get(Space, source.id)
        assert await db.get(Expense, saved_expense.id)
        assert await db.scalar(
            select(SpaceMember.id).where(
                SpaceMember.space_id == source.id, SpaceMember.user_id == actor.id
            )
        )
        assert not await db.scalar(
            select(SpaceMember.id).where(
                SpaceMember.space_id == destination.id, SpaceMember.user_id == actor.id
            )
        )
        assert (await db.get(InviteLink, invite.id)).used_at is None


async def test_payment_method_list_has_constant_query_count(real_db):
    """The actual API batches metadata while preserving all ownership rules."""
    owner = await real_db.user("Current owner")
    other = await real_db.user("Other current owner")
    former = await real_db.user("Former method owner")
    space = await real_db.space(owner)
    await real_db.member(space, other)
    await real_db.member(space, former)
    async with real_db.sessions() as db:
        db.add(PaymentMethod(space_id=space.id, owner_id=owner.id, label="Card 0"))
        await db.commit()

    async def dependency():
        async with real_db.sessions() as db:
            yield db

    async def counted_list(client):
        queries = []

        def record(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                queries.append(statement)

        event.listen(real_db.engine.sync_engine, "before_cursor_execute", record)
        try:
            response = await client.get(f"/api/v1/spaces/{space.id}/payment-methods")
        finally:
            event.remove(real_db.engine.sync_engine, "before_cursor_execute", record)
        assert response.status_code == 200
        return response.json(), len(queries)

    app.dependency_overrides[get_db] = dependency
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            client.cookies.set("access_token", create_access_token(owner.id))
            first, first_count = await counted_list(client)
            assert len(first) == 2
            async with real_db.sessions() as db:
                owners = (owner, other, former)
                db.add_all(
                    [
                        PaymentMethod(
                            space_id=space.id,
                            owner_id=owners[index % 3].id,
                            label=f"Card {index}",
                        )
                        for index in range(1, 20)
                    ]
                )
                await db.commit()
            confirmation = await real_db.confirmation(space, former)
            async with real_db.sessions() as db:
                await leave_space(db, space.id, former.id, confirmation)
            methods, large_count = await counted_list(client)
            assert len(methods) == 21
            assert first_count == large_count == 5
            for method in methods:
                if method["is_system"]:
                    assert not method["can_manage"]
                    assert method["owner_display_name"] is None
                elif method["owner_id"] == str(former.id):
                    assert method["can_manage"]
                    assert not method["owner_is_member"]
                    assert method["owner_display_name"] == former.display_name
                else:
                    assert method["owner_is_member"]
                    assert method["can_manage"] == (method["owner_id"] == str(owner.id))
    finally:
        app.dependency_overrides.pop(get_db, None)
