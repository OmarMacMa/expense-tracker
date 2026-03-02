from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Category, ExpenseLine
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services.expense import (
    build_expense_response,
    create_expense,
    delete_expense,
    get_expense,
    list_expenses,
    update_expense,
)


async def _get_uncategorized_id(db, space_id):
    """Helper to get the Uncategorized category ID."""
    stmt = select(Category).where(
        Category.space_id == space_id, Category.is_system.is_(True)
    )
    result = await db.execute(stmt)
    return result.scalar_one().id


@pytest.mark.asyncio
async def test_create_expense_basic(db_session, test_user, test_space):
    """Basic expense creation succeeds."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    data = ExpenseCreate(
        merchant="Walmart",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("42.50"),
        category_id=cat_id,
        spender_id=test_user.id,
    )
    expense = await create_expense(db_session, test_space.id, data, test_user.id)

    assert expense.id is not None
    assert expense.merchant == "Walmart"
    assert expense.total_amount == Decimal("42.50")
    assert expense.status == "confirmed"


@pytest.mark.asyncio
async def test_create_expense_with_tags(db_session, test_user, test_space):
    """Tags are auto-created and attached to the expense line."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    data = ExpenseCreate(
        merchant="Target",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("25.00"),
        category_id=cat_id,
        spender_id=test_user.id,
        tags=["groceries", "weekly"],
    )
    expense = await create_expense(db_session, test_space.id, data, test_user.id)
    response = await build_expense_response(db_session, expense)

    assert len(response["lines"]) == 1
    tag_names = {t["name"] for t in response["lines"][0]["tags"]}
    assert tag_names == {"groceries", "weekly"}


@pytest.mark.asyncio
async def test_create_expense_future_date_422(db_session, test_user, test_space):
    """Future purchase datetime is rejected with 422."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    data = ExpenseCreate(
        merchant="Walmart",
        purchase_datetime=datetime.now(UTC) + timedelta(days=1),
        amount=Decimal("10.00"),
        category_id=cat_id,
        spender_id=test_user.id,
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_expense(db_session, test_space.id, data, test_user.id)
    assert exc_info.value.status_code == 422
    assert "future" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_create_expense_line_exists(db_session, test_user, test_space):
    """Expense creation creates a corresponding expense line."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    data = ExpenseCreate(
        merchant="Target",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("15.00"),
        category_id=cat_id,
        spender_id=test_user.id,
    )
    expense = await create_expense(db_session, test_space.id, data, test_user.id)

    line_stmt = select(ExpenseLine).where(ExpenseLine.expense_id == expense.id)
    line_result = await db_session.execute(line_stmt)
    line = line_result.scalar_one()

    assert line.amount == Decimal("15.00")
    assert line.category_id == cat_id
    assert line.line_order == 0


@pytest.mark.asyncio
async def test_get_expense(db_session, test_user, test_space):
    """Getting an expense returns the correct one."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    data = ExpenseCreate(
        merchant="Costco",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("100.00"),
        category_id=cat_id,
        spender_id=test_user.id,
    )
    expense = await create_expense(db_session, test_space.id, data, test_user.id)

    fetched = await get_expense(db_session, test_space.id, expense.id)
    assert fetched is not None
    assert fetched.id == expense.id
    assert fetched.merchant == "Costco"


@pytest.mark.asyncio
async def test_update_expense_amount(db_session, test_user, test_space):
    """Updating amount changes both header and line."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    data = ExpenseCreate(
        merchant="Walmart",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("50.00"),
        category_id=cat_id,
        spender_id=test_user.id,
    )
    expense = await create_expense(db_session, test_space.id, data, test_user.id)

    update_data = ExpenseUpdate(amount=Decimal("75.00"))
    updated = await update_expense(db_session, test_space.id, expense.id, update_data)

    assert updated.total_amount == Decimal("75.00")

    # Check line was also updated
    line_stmt = select(ExpenseLine).where(ExpenseLine.expense_id == expense.id)
    line_result = await db_session.execute(line_stmt)
    line = line_result.scalar_one()
    assert line.amount == Decimal("75.00")


@pytest.mark.asyncio
async def test_update_expense_partial(db_session, test_user, test_space):
    """Partial update only changes sent fields."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    data = ExpenseCreate(
        merchant="Walmart",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("30.00"),
        category_id=cat_id,
        spender_id=test_user.id,
        notes="original notes",
    )
    expense = await create_expense(db_session, test_space.id, data, test_user.id)

    update_data = ExpenseUpdate(notes="updated notes")
    updated = await update_expense(db_session, test_space.id, expense.id, update_data)

    assert updated.notes == "updated notes"
    assert updated.merchant == "Walmart"  # unchanged
    assert updated.total_amount == Decimal("30.00")  # unchanged


@pytest.mark.asyncio
async def test_delete_expense(db_session, test_user, test_space):
    """Deleting removes the expense and cascades to lines."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)
    data = ExpenseCreate(
        merchant="Target",
        purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
        amount=Decimal("20.00"),
        category_id=cat_id,
        spender_id=test_user.id,
    )
    expense = await create_expense(db_session, test_space.id, data, test_user.id)
    expense_id = expense.id

    await delete_expense(db_session, test_space.id, expense_id)

    # Expense gone
    fetched = await get_expense(db_session, test_space.id, expense_id)
    assert fetched is None

    # Line also gone (CASCADE)
    line_stmt = select(ExpenseLine).where(ExpenseLine.expense_id == expense_id)
    line_result = await db_session.execute(line_stmt)
    assert line_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_list_expenses_pagination(db_session, test_user, test_space):
    """Cursor pagination returns correct pages."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)

    # Create 15 expenses
    for i in range(15):
        data = ExpenseCreate(
            merchant=f"Store {i}",
            purchase_datetime=datetime.now(UTC) - timedelta(hours=15 - i),
            amount=Decimal("10.00"),
            category_id=cat_id,
            spender_id=test_user.id,
        )
        await create_expense(db_session, test_space.id, data, test_user.id)

    # First page
    result = await list_expenses(db_session, test_space.id, limit=10)
    assert len(result["data"]) == 10
    assert result["next_cursor"] is not None

    # Second page
    result2 = await list_expenses(
        db_session, test_space.id, cursor=result["next_cursor"], limit=10
    )
    assert len(result2["data"]) == 5
    assert result2["next_cursor"] is None


@pytest.mark.asyncio
async def test_list_expenses_search(db_session, test_user, test_space):
    """Search finds expenses by merchant name."""
    cat_id = await _get_uncategorized_id(db_session, test_space.id)

    await create_expense(
        db_session,
        test_space.id,
        ExpenseCreate(
            merchant="Walmart Supercenter",
            purchase_datetime=datetime.now(UTC) - timedelta(hours=1),
            amount=Decimal("50.00"),
            category_id=cat_id,
            spender_id=test_user.id,
        ),
        test_user.id,
    )

    await create_expense(
        db_session,
        test_space.id,
        ExpenseCreate(
            merchant="Target",
            purchase_datetime=datetime.now(UTC) - timedelta(hours=2),
            amount=Decimal("30.00"),
            category_id=cat_id,
            spender_id=test_user.id,
        ),
        test_user.id,
    )

    result = await list_expenses(db_session, test_space.id, search="walmart")
    assert len(result["data"]) == 1
    assert result["data"][0]["merchant"] == "Walmart Supercenter"
