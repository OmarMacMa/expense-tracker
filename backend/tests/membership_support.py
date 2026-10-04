"""Real connections/commits and exact cleanup, restricted to a local test DB."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import TracebackType

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models import (
    Category,
    Expense,
    ExpenseLine,
    InviteLink,
    Limit,
    LimitFilter,
    Merchant,
    MonthlyWrap,
    PaymentMethod,
    RecurringTemplate,
    Space,
    SpaceMember,
    Tag,
    User,
)
from app.models.expense import expense_line_tags
from app.schemas.space import LeaveConfirmation, SpaceCreate
from app.services.membership import SPACE_DATA, leave_preview
from app.services.space import create_space


class MembershipDatabase:
    def __init__(self) -> None:
        url = make_url(settings.DATABASE_URL)
        if url.host not in ("localhost", "127.0.0.1") or not (
            url.database and url.database.endswith("_test")
        ):
            raise RuntimeError("Real membership tests require a local *_test database")
        self.engine = create_async_engine(settings.DATABASE_URL)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.user_ids: list[uuid.UUID] = []
        self.space_ids: list[uuid.UUID] = []

    async def __aenter__(self) -> "MembershipDatabase":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        async with self.sessions() as db:
            # Only IDs created by this fixture, never whole-table cleanup.
            for model in SPACE_DATA:
                await db.execute(
                    delete(model).where(model.space_id.in_(self.space_ids))
                )
            await db.execute(
                delete(SpaceMember).where(SpaceMember.space_id.in_(self.space_ids))
            )
            await db.execute(delete(Space).where(Space.id.in_(self.space_ids)))
            await db.execute(delete(User).where(User.id.in_(self.user_ids)))
            await db.commit()
        await self.engine.dispose()

    async def user(self, name: str = "Invite Test") -> User:
        async with self.sessions() as db:
            unique = uuid.uuid4().hex
            user = User(
                google_id=f"membership_{unique}",
                email=f"{unique}@example.test",
                display_name=name,
            )
            db.add(user)
            await db.commit()
            self.user_ids.append(user.id)
            return user

    async def space(self, owner: User, name: str = "Source") -> Space:
        async with self.sessions() as db:
            space = await create_space(
                db,
                owner,
                SpaceCreate(
                    name=name,
                    currency_code="USD",
                    timezone="UTC",
                ),
            )
            self.space_ids.append(space.id)
            return space

    async def invite(self, space: Space, owner: User, **kwargs: object) -> InviteLink:
        async with self.sessions() as db:
            invite = InviteLink(
                space_id=space.id,
                created_by=owner.id,
                token=uuid.uuid4().hex,
                expires_at=datetime.now(UTC) + timedelta(days=7),
                **kwargs,
            )
            db.add(invite)
            await db.commit()
            return invite

    async def member(self, space: Space, user: User) -> None:
        async with self.sessions() as db:
            db.add(SpaceMember(space_id=space.id, user_id=user.id))
            await db.commit()

    async def confirmation(self, space: Space, user: User) -> LeaveConfirmation:
        async with self.sessions() as db:
            preview = await leave_preview(db, space.id, user.id)
            return LeaveConfirmation(source_name=preview.space_name, preview=preview)

    async def populate(self, space: Space, owner: User) -> dict[str, uuid.UUID]:
        """Populate every owned table and both expense statuses."""
        async with self.sessions() as db:
            category = await db.scalar(
                select(Category).where(Category.space_id == space.id)
            )
            assert category
            pm = PaymentMethod(space_id=space.id, owner_id=owner.id, label="Old card")
            tag = Tag(space_id=space.id, name="historical")
            db.add_all([pm, tag])
            await db.flush()
            template = RecurringTemplate(
                space_id=space.id,
                name="Dormant",
                schedule="monthly",
                default_amount=Decimal("12"),
                default_merchant="History",
                default_category_id=category.id,
                default_spender_id=owner.id,
                default_payment_method_id=pm.id,
                next_due_date=date.today(),
            )
            limit = Limit(
                space_id=space.id,
                name="Budget",
                timeframe="monthly",
                threshold_amount=Decimal("100"),
            )
            db.add_all([template, limit])
            await db.flush()
            db.add_all(
                [
                    LimitFilter(
                        limit_id=limit.id,
                        filter_type="category",
                        filter_value=str(category.id),
                    ),
                    Merchant(
                        space_id=space.id,
                        name="History",
                        normalized_name="history",
                        last_category_id=category.id,
                    ),
                    MonthlyWrap(
                        space_id=space.id, year=2025, month=1, data={"total": "12"}
                    ),
                    InviteLink(
                        space_id=space.id,
                        created_by=owner.id,
                        token=uuid.uuid4().hex,
                        expires_at=datetime.now(UTC) + timedelta(days=7),
                    ),
                ]
            )
            first_id = None
            for status in ("pending", "confirmed"):
                expense = Expense(
                    space_id=space.id,
                    merchant="History",
                    merchant_normalized="history",
                    purchase_datetime=datetime.now(UTC) - timedelta(days=2),
                    total_amount=Decimal("12"),
                    spender_id=owner.id,
                    payment_method_id=pm.id,
                    recurring_template_id=template.id,
                    status=status,
                )
                db.add(expense)
                await db.flush()
                line = ExpenseLine(
                    expense_id=expense.id,
                    amount=Decimal("12"),
                    category_id=category.id,
                    line_order=0,
                )
                db.add(line)
                await db.flush()
                await db.execute(
                    expense_line_tags.insert().values(
                        expense_line_id=line.id,
                        tag_id=tag.id,
                    )
                )
                first_id = expense.id
            await db.commit()
            assert first_id
            return {"expense": first_id, "method": pm.id, "category": category.id}


async def run_operation(database: MembershipDatabase, operation) -> object:
    """Run a transition on its own connection, with real commits."""
    async with database.sessions() as db:
        try:
            return await operation(db)
        except Exception as error:
            await db.rollback()
            return error
