import base64
import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Expense, ExpenseLine, Tag, User
from app.models.expense import expense_line_tags
from app.services.merchant import upsert_merchant
from app.services.tag import ensure_tags


async def create_expense(
    db: AsyncSession, space_id: uuid.UUID, data, user_id: uuid.UUID
) -> Expense:
    """Create an expense with a single line, tags, and merchant upsert."""
    # Validate: no future dates
    if data.purchase_datetime.tzinfo is None:
        purchase_dt = data.purchase_datetime.replace(tzinfo=UTC)
    else:
        purchase_dt = data.purchase_datetime

    if purchase_dt > datetime.now(UTC):
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "FUTURE_DATE",
                    "message": "Expenses cannot have a future purchase date",
                }
            },
        )

    if len(data.tags) > 10:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "TOO_MANY_TAGS",
                    "message": "Maximum 10 tags per expense line",
                }
            },
        )

    merchant_normalized = data.merchant.strip().lower()

    expense = Expense(
        space_id=space_id,
        merchant=data.merchant.strip(),
        merchant_normalized=merchant_normalized,
        purchase_datetime=purchase_dt,
        total_amount=data.amount,
        spender_id=data.spender_id,
        payment_method_id=data.payment_method_id,
        notes=data.notes,
        status="confirmed",
    )
    db.add(expense)
    await db.flush()

    line = ExpenseLine(
        expense_id=expense.id,
        amount=data.amount,
        category_id=data.category_id,
        line_order=0,
    )
    db.add(line)
    await db.flush()

    if data.tags:
        tags = await ensure_tags(db, space_id, data.tags)
        for tag in tags:
            stmt = expense_line_tags.insert().values(
                expense_line_id=line.id, tag_id=tag.id
            )
            await db.execute(stmt)

    await upsert_merchant(db, space_id, data.merchant, data.category_id)

    # Limit progress is computed on-read (not stored), so no recalculation needed here

    await db.commit()
    await db.refresh(expense)

    return expense


async def build_expense_response(db: AsyncSession, expense: Expense) -> dict:
    """Build a full expense response dict with line, tags, spender info."""
    spender_stmt = select(User).where(User.id == expense.spender_id)
    spender_result = await db.execute(spender_stmt)
    spender = spender_result.scalar_one()

    lines_stmt = (
        select(ExpenseLine)
        .options(selectinload(ExpenseLine.tags), selectinload(ExpenseLine.category))
        .where(ExpenseLine.expense_id == expense.id)
        .order_by(ExpenseLine.line_order)
    )
    lines_result = await db.execute(lines_stmt)
    lines = lines_result.scalars().all()

    return {
        "id": expense.id,
        "space_id": expense.space_id,
        "merchant": expense.merchant,
        "purchase_datetime": expense.purchase_datetime,
        "total_amount": expense.total_amount,
        "spender": {
            "id": spender.id,
            "display_name": spender.display_name,
            "email": spender.email,
        },
        "payment_method_id": expense.payment_method_id,
        "notes": expense.notes,
        "status": expense.status,
        "lines": [
            {
                "id": line.id,
                "amount": line.amount,
                "category_id": line.category_id,
                "category_name": line.category.name if line.category else None,
                "line_order": line.line_order,
                "tags": [{"id": t.id, "name": t.name} for t in line.tags],
            }
            for line in lines
        ],
        "created_at": expense.created_at,
        "updated_at": expense.updated_at,
    }


async def list_expenses(
    db: AsyncSession,
    space_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = 20,
    spender_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    merchant: str | None = None,
    tag: str | None = None,
    payment_method_id: uuid.UUID | None = None,
    search: str | None = None,
    period: str | None = None,
    month: str | None = None,
) -> dict:
    """List expenses with cursor pagination and filters.

    Cursor = base64 encoded JSON: {"dt": iso_datetime, "id": uuid_string}
    Sort: purchase_datetime DESC, id DESC
    """
    stmt = (
        select(Expense)
        .where(Expense.space_id == space_id)
        .order_by(Expense.purchase_datetime.desc(), Expense.id.desc())
        .limit(limit + 1)
    )

    # Apply cursor
    if cursor:
        try:
            cursor_data = json.loads(base64.b64decode(cursor).decode())
            cursor_dt = datetime.fromisoformat(cursor_data["dt"])
            cursor_id = uuid.UUID(cursor_data["id"])
            stmt = stmt.where(
                or_(
                    Expense.purchase_datetime < cursor_dt,
                    and_(
                        Expense.purchase_datetime == cursor_dt,
                        Expense.id < cursor_id,
                    ),
                )
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_CURSOR",
                        "message": "Invalid cursor format",
                    }
                },
            )

    # Apply filters
    if spender_id:
        stmt = stmt.where(Expense.spender_id == spender_id)

    if payment_method_id:
        stmt = stmt.where(Expense.payment_method_id == payment_method_id)

    if merchant:
        stmt = stmt.where(Expense.merchant_normalized.ilike(f"%{merchant.lower()}%"))

    if category_id:
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id).where(
                    ExpenseLine.category_id == category_id
                )
            )
        )

    if tag:
        tag_normalized = tag.strip().lower().lstrip("#")
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id)
                .join(
                    expense_line_tags,
                    ExpenseLine.id == expense_line_tags.c.expense_line_id,
                )
                .join(Tag, expense_line_tags.c.tag_id == Tag.id)
                .where(Tag.name == tag_normalized)
            )
        )

    if search:
        search_term = f"%{search.lower()}%"
        tag_subquery = (
            select(ExpenseLine.expense_id)
            .join(
                expense_line_tags,
                ExpenseLine.id == expense_line_tags.c.expense_line_id,
            )
            .join(Tag, expense_line_tags.c.tag_id == Tag.id)
            .where(Tag.name.ilike(search_term))
        )
        stmt = stmt.where(
            or_(
                Expense.merchant_normalized.ilike(search_term),
                func.lower(Expense.notes).ilike(search_term),
                Expense.id.in_(tag_subquery),
            )
        )

    # Period/month filters (Phase 7 TimeWindowResolver will handle properly)
    if month:
        try:
            year, m = month.split("-")
            start = datetime(int(year), int(m), 1, tzinfo=UTC)
            if int(m) == 12:
                end = datetime(int(year) + 1, 1, 1, tzinfo=UTC)
            else:
                end = datetime(int(year), int(m) + 1, 1, tzinfo=UTC)
            stmt = stmt.where(
                Expense.purchase_datetime >= start,
                Expense.purchase_datetime < end,
            )
        except (ValueError, IndexError):
            pass

    if period:
        now = datetime.now(UTC)
        if period == "this_month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            stmt = stmt.where(Expense.purchase_datetime >= start)
        elif period == "last_month":
            first_of_this = now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            if now.month == 1:
                first_of_last = first_of_this.replace(year=now.year - 1, month=12)
            else:
                first_of_last = first_of_this.replace(month=now.month - 1)
            stmt = stmt.where(
                Expense.purchase_datetime >= first_of_last,
                Expense.purchase_datetime < first_of_this,
            )

    result = await db.execute(stmt)
    expenses = result.scalars().all()

    has_more = len(expenses) > limit
    if has_more:
        expenses = expenses[:limit]

    data = []
    for exp in expenses:
        response = await build_expense_response(db, exp)
        data.append(response)

    next_cursor = None
    if has_more and expenses:
        last = expenses[-1]
        cursor_obj = {
            "dt": last.purchase_datetime.isoformat(),
            "id": str(last.id),
        }
        next_cursor = base64.b64encode(json.dumps(cursor_obj).encode()).decode()

    return {"data": data, "next_cursor": next_cursor}


async def get_expense(
    db: AsyncSession, space_id: uuid.UUID, expense_id: uuid.UUID
) -> Expense | None:
    """Get expense by ID within space."""
    stmt = select(Expense).where(
        Expense.space_id == space_id,
        Expense.id == expense_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def update_expense(
    db: AsyncSession, space_id: uuid.UUID, expense_id: uuid.UUID, data
) -> Expense:
    """Partial update of an expense. Only updates sent fields.

    When amount changes, updates both expense.total_amount and the sole line.amount.
    Sets updated_at = now in service layer.
    """
    expense = await get_expense(db, space_id, expense_id)
    if expense is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Expense not found"}},
        )

    update_data = data.model_dump(exclude_unset=True)

    if "purchase_datetime" in update_data and update_data["purchase_datetime"]:
        dt = update_data["purchase_datetime"]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        if dt > datetime.now(UTC):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "FUTURE_DATE",
                        "message": "Expenses cannot have a future purchase date",
                    }
                },
            )
        expense.purchase_datetime = dt

    if "merchant" in update_data and update_data["merchant"]:
        expense.merchant = update_data["merchant"].strip()
        expense.merchant_normalized = update_data["merchant"].strip().lower()

    if "spender_id" in update_data:
        expense.spender_id = update_data["spender_id"]

    if "payment_method_id" in update_data:
        expense.payment_method_id = update_data["payment_method_id"]

    if "notes" in update_data:
        expense.notes = update_data["notes"]

    # Helper to fetch the sole expense line
    async def _get_sole_line() -> ExpenseLine | None:
        line_stmt = (
            select(ExpenseLine)
            .where(ExpenseLine.expense_id == expense.id)
            .order_by(ExpenseLine.line_order)
        )
        line_result = await db.execute(line_stmt)
        return line_result.scalar_one_or_none()

    # Handle amount change — update both header and sole line
    if "amount" in update_data and update_data["amount"] is not None:
        expense.total_amount = update_data["amount"]
        line = await _get_sole_line()
        if line:
            line.amount = update_data["amount"]

    # Handle category change — update line + re-upsert merchant
    if "category_id" in update_data and update_data["category_id"] is not None:
        line = await _get_sole_line()
        if line:
            line.category_id = update_data["category_id"]
        await upsert_merchant(
            db, space_id, expense.merchant, update_data["category_id"]
        )

    # Handle tags change — replace all tags on the line
    if "tags" in update_data and update_data["tags"] is not None:
        line = await _get_sole_line()
        if line:
            await db.execute(
                delete(expense_line_tags).where(
                    expense_line_tags.c.expense_line_id == line.id
                )
            )
            if update_data["tags"]:
                tags = await ensure_tags(db, space_id, update_data["tags"])
                for tag_obj in tags:
                    await db.execute(
                        expense_line_tags.insert().values(
                            expense_line_id=line.id, tag_id=tag_obj.id
                        )
                    )

    # Set updated_at in service layer
    expense.updated_at = datetime.now(UTC)

    # Limit progress is computed on-read (not stored), so no recalculation needed here

    await db.commit()
    await db.refresh(expense)
    return expense


async def delete_expense(
    db: AsyncSession, space_id: uuid.UUID, expense_id: uuid.UUID
) -> bool:
    """Hard delete an expense. CASCADE handles lines and line_tags.

    Returns True if deleted, raises 404 if not found.
    """
    expense = await get_expense(db, space_id, expense_id)
    if expense is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Expense not found"}},
        )

    await db.delete(expense)
    await db.commit()

    # Limit progress is computed on-read (not stored), so no recalculation needed here

    return True
