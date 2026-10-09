import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.space import get_current_space_member
from app.models import SpaceMember
from app.routers.amount_range import get_amount_range
from app.schemas.amount_range import AmountRange
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseUpdate,
)
from app.services.expense import (
    build_expense_response,
    create_expense,
    delete_expense,
    get_expense,
    list_expenses,
    update_expense,
)

router = APIRouter(prefix="/api/v1/spaces/{space_id}", tags=["expenses"])


@router.post("/expenses", response_model=ExpenseResponse, status_code=201)
async def create_expense_endpoint(
    space_id: uuid.UUID,
    data: ExpenseCreate,
    member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    """Create a new expense."""
    expense = await create_expense(db, space_id, data, member.user_id)
    response_data = await build_expense_response(db, expense)
    return ExpenseResponse(**response_data)


@router.get("/expenses", response_model=ExpenseListResponse)
async def list_expenses_endpoint(
    space_id: uuid.UUID,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    period: str | None = Query(None),
    month: str | None = Query(None),
    spender: list[uuid.UUID] | None = Query(None),
    category: list[uuid.UUID] | None = Query(None),
    merchant: list[str] | None = Query(None),
    tag: list[str] | None = Query(None),
    payment_method: list[uuid.UUID] | None = Query(None),
    search: str | None = Query(None),
    amount_range: AmountRange = Depends(get_amount_range),
    status: Literal["confirmed", "pending"] | None = Query(None),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> ExpenseListResponse:
    """List expenses with cursor pagination and filters."""
    result = await list_expenses(
        db,
        space_id,
        cursor=cursor,
        limit=limit,
        spender_id=spender,
        category_id=category,
        merchant=merchant,
        tag=tag,
        payment_method_id=payment_method,
        search=search,
        status=status,
        period=period,
        month=month,
        min_amount=amount_range.min_amount,
        max_amount=amount_range.max_amount,
    )
    return ExpenseListResponse(
        data=[ExpenseResponse(**d) for d in result["data"]],
        next_cursor=result["next_cursor"],
    )


@router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
async def get_expense_endpoint(
    space_id: uuid.UUID,
    expense_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    """Get full expense detail."""
    expense = await get_expense(db, space_id, expense_id)
    if expense is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "NOT_FOUND", "message": "Expense not found"}},
        )
    response_data = await build_expense_response(db, expense)
    return ExpenseResponse(**response_data)


@router.patch("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense_endpoint(
    space_id: uuid.UUID,
    expense_id: uuid.UUID,
    data: ExpenseUpdate,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    """Partial update an expense."""
    expense = await update_expense(db, space_id, expense_id, data)
    response_data = await build_expense_response(db, expense)
    return ExpenseResponse(**response_data)


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense_endpoint(
    space_id: uuid.UUID,
    expense_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Hard delete an expense."""
    await delete_expense(db, space_id, expense_id)
