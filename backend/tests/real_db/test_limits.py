from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.db.session import get_db
from app.main import app
from app.models import Category, Expense, ExpenseLine, Limit, LimitFilter, Space
from app.services.time_window import TimeWindowResolver


@pytest_asyncio.fixture
async def limit_client(real_db) -> AsyncGenerator[AsyncClient, None]:
    async def dependency() -> AsyncGenerator[AsyncSession, None]:
        async with real_db.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = dependency
    try:
        yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    finally:
        app.dependency_overrides.pop(get_db, None)


async def test_timeframe_patch_persists_and_recalculates(
    real_db, monkeypatch, limit_client
):
    """Real commits and fresh connections, including DST-local boundaries."""
    actor = await real_db.user("Limit Owner")
    outsider = await real_db.user("Other Owner")
    space = await real_db.space(actor)
    foreign = await real_db.space(outsider, "Other Space")
    reference = datetime(2026, 3, 11, 12, tzinfo=UTC)
    resolver = TimeWindowResolver("America/New_York")
    weekly_start, _ = resolver.get_current_window("weekly", reference)
    monthly_start, _ = resolver.get_current_window("monthly", reference)
    assert weekly_start == datetime(2026, 3, 9, 4, tzinfo=UTC)
    assert monthly_start == datetime(2026, 3, 1, 5, tzinfo=UTC)
    original_window = TimeWindowResolver.get_current_window
    monkeypatch.setattr(
        TimeWindowResolver,
        "get_current_window",
        lambda self, timeframe, ref_date=None: original_window(
            self, timeframe, reference if ref_date is None else ref_date
        ),
    )
    async with real_db.sessions() as db:
        stored_space = await db.get(Space, space.id)
        stored_space.timezone = "America/New_York"
        category = Category(
            space_id=space.id, name="Groceries", normalized_name="groceries"
        )
        other_category = await db.scalar(
            select(Category).where(Category.space_id == space.id)
        )
        foreign_category = await db.scalar(
            select(Category).where(Category.space_id == foreign.id)
        )
        target = Limit(
            space_id=space.id,
            name="Budget",
            timeframe="monthly",
            threshold_amount=Decimal("100"),
            warning_pct=Decimal("0.75"),
        )
        control = Limit(
            space_id=space.id,
            name="Control",
            timeframe="monthly",
            threshold_amount=Decimal("1000"),
        )
        foreign_limit = Limit(
            space_id=foreign.id,
            name="Foreign",
            timeframe="monthly",
            threshold_amount=Decimal("2000"),
        )
        db.add_all([category, target, control, foreign_limit])
        await db.flush()
        db.add(
            LimitFilter(
                limit_id=target.id,
                filter_type="category",
                filter_value=str(category.id),
            )
        )
        for owner, tenant, cat, when, amount, status in (
            (actor, space, category, weekly_start, "80", "confirmed"),
            (
                actor,
                space,
                category,
                weekly_start - timedelta(microseconds=1),
                "20",
                "confirmed",
            ),
            (
                actor,
                space,
                category,
                monthly_start - timedelta(microseconds=1),
                "100",
                "confirmed",
            ),
            (actor, space, category, weekly_start, "900", "pending"),
            (actor, space, other_category, weekly_start, "700", "confirmed"),
            (outsider, foreign, foreign_category, weekly_start, "500", "confirmed"),
        ):
            expense = Expense(
                space_id=tenant.id,
                spender_id=owner.id,
                merchant="Store",
                merchant_normalized="store",
                purchase_datetime=when,
                total_amount=Decimal(amount),
                status=status,
            )
            db.add(expense)
            await db.flush()
            db.add(
                ExpenseLine(
                    expense_id=expense.id,
                    category_id=cat.id,
                    amount=Decimal(amount),
                    line_order=0,
                )
            )
        await db.commit()

    path = f"/api/v1/spaces/{space.id}"
    limit_client.cookies.set("access_token", create_access_token(actor.id))
    async with limit_client as client:
        for timeframe, spent, status in (
            ("weekly", "80", "warning"),
            ("monthly", "100", "critical"),
        ):
            response = await client.patch(
                f"{path}/limits/{target.id}", json={"timeframe": timeframe}
            )
            assert response.status_code == 200
            result = response.json()
            assert result["id"] == str(target.id)
            assert result["timeframe"] == timeframe
            assert Decimal(result["spent"]) == Decimal(spent)
            assert Decimal(result["progress"]) == Decimal(spent) / 100
            assert result["status"] == status
            assert Decimal(result["threshold_amount"]) == Decimal("100")
            assert Decimal(result["warning_pct"]) == Decimal("0.75")
            assert result["filters"][0]["filter_value"] == str(category.id)
            assert result["filters"][0]["filter_display_name"] == "Groceries"
            for endpoint in ("limits", "insights/limit-progress"):
                read = await client.get(f"{path}/{endpoint}")
                assert read.status_code == 200
                actual = next(x for x in read.json() if x["id"] == str(target.id))
                assert actual == result
                assert all(x["id"] != str(foreign_limit.id) for x in read.json())
            async with real_db.sessions() as db:
                persisted = await db.get(Limit, target.id)
                assert persisted.timeframe == timeframe
                assert persisted.warning_pct == Decimal("0.75")
                assert (await db.get(Limit, control.id)).timeframe == "monthly"
                assert (await db.get(Limit, foreign_limit.id)).timeframe == "monthly"

        omitted = await client.patch(
            f"{path}/limits/{target.id}", json={"name": "Renamed"}
        )
        assert omitted.status_code == 200
        assert omitted.json()["timeframe"] == "monthly"
        denied = await client.patch(
            f"{path}/limits/{foreign_limit.id}", json={"timeframe": "weekly"}
        )
        assert denied.status_code == 404
        denied = await client.patch(
            f"/api/v1/spaces/{foreign.id}/limits/{foreign_limit.id}",
            json={"timeframe": "weekly"},
        )
        assert denied.status_code == 403
        assert (
            await client.get(f"/api/v1/spaces/{foreign.id}/limits")
        ).status_code == 403


@pytest.mark.parametrize("timeframe", ["quarterly", "yearly", "Weekly", "", None, 7])
async def test_invalid_timeframe_is_atomic(real_db, timeframe, limit_client):
    actor = await real_db.user()
    space = await real_db.space(actor)
    async with real_db.sessions() as db:
        target = Limit(
            space_id=space.id,
            name="Unchanged",
            timeframe="monthly",
            threshold_amount=Decimal("100"),
        )
        db.add(target)
        await db.commit()
    limit_client.cookies.set("access_token", create_access_token(actor.id))
    async with limit_client as client:
        response = await client.patch(
            f"/api/v1/spaces/{space.id}/limits/{target.id}",
            json={"timeframe": timeframe, "name": "Must not save", "filters": []},
        )
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert any(
            detail["field"] == "body.timeframe" and detail["message"]
            for detail in error["details"]
        )
    async with real_db.sessions() as db:
        persisted = await db.get(Limit, target.id)
        assert persisted.name == "Unchanged"
        assert persisted.timeframe == "monthly"
