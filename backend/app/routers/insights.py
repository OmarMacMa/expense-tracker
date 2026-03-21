import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.space import get_current_space_member
from app.models import SpaceMember
from app.schemas.insight import (
    CategoryBreakdownItem,
    MerchantLeaderboardItem,
    SpenderBreakdownItem,
    SpendingTrendResponse,
    SummaryResponse,
)
from app.schemas.limit import LimitResponse
from app.services.insight import (
    get_category_breakdown,
    get_merchant_leaderboard,
    get_spender_breakdown,
    get_spending_trend,
    get_summary,
)
from app.services.limit import list_limits_with_progress

router = APIRouter(prefix="/api/v1/spaces/{space_id}/insights", tags=["insights"])


@router.get("/summary", response_model=SummaryResponse)
async def summary_endpoint(
    space_id: uuid.UUID,
    period: str | None = Query(None),
    month: str | None = Query(None),
    spender: uuid.UUID | None = Query(None),
    category: uuid.UUID | None = Query(None),
    merchant: str | None = Query(None),
    tag: str | None = Query(None),
    payment_method: uuid.UUID | None = Query(None),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    result = await get_summary(
        db,
        space_id,
        period=period,
        month=month,
        spender_id=spender,
        category_id=category,
        merchant=merchant,
        tag=tag,
        payment_method_id=payment_method,
    )
    return SummaryResponse(**result)


@router.get("/spending-trend", response_model=SpendingTrendResponse)
async def spending_trend_endpoint(
    space_id: uuid.UUID,
    period: str | None = Query(None),
    month: str | None = Query(None),
    spender: uuid.UUID | None = Query(None),
    category: uuid.UUID | None = Query(None),
    merchant: str | None = Query(None),
    tag: str | None = Query(None),
    payment_method: uuid.UUID | None = Query(None),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> SpendingTrendResponse:
    result = await get_spending_trend(
        db,
        space_id,
        period=period,
        month=month,
        spender_id=spender,
        category_id=category,
        merchant=merchant,
        tag=tag,
        payment_method_id=payment_method,
    )
    return SpendingTrendResponse(**result)


@router.get("/category-breakdown", response_model=list[CategoryBreakdownItem])
async def category_breakdown_endpoint(
    space_id: uuid.UUID,
    period: str | None = Query(None),
    month: str | None = Query(None),
    spender: uuid.UUID | None = Query(None),
    merchant: str | None = Query(None),
    tag: str | None = Query(None),
    payment_method: uuid.UUID | None = Query(None),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryBreakdownItem]:
    result = await get_category_breakdown(
        db,
        space_id,
        period=period,
        month=month,
        spender_id=spender,
        merchant=merchant,
        tag=tag,
        payment_method_id=payment_method,
    )
    return [CategoryBreakdownItem(**item) for item in result]


@router.get("/merchant-leaderboard", response_model=list[MerchantLeaderboardItem])
async def merchant_leaderboard_endpoint(
    space_id: uuid.UUID,
    period: str | None = Query(None),
    month: str | None = Query(None),
    spender: uuid.UUID | None = Query(None),
    category: uuid.UUID | None = Query(None),
    tag: str | None = Query(None),
    payment_method: uuid.UUID | None = Query(None),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[MerchantLeaderboardItem]:
    result = await get_merchant_leaderboard(
        db,
        space_id,
        period=period,
        month=month,
        spender_id=spender,
        category_id=category,
        tag=tag,
        payment_method_id=payment_method,
    )
    return [MerchantLeaderboardItem(**item) for item in result]


@router.get("/spender-breakdown", response_model=list[SpenderBreakdownItem])
async def spender_breakdown_endpoint(
    space_id: uuid.UUID,
    period: str | None = Query(None),
    month: str | None = Query(None),
    category: uuid.UUID | None = Query(None),
    merchant: str | None = Query(None),
    tag: str | None = Query(None),
    payment_method: uuid.UUID | None = Query(None),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[SpenderBreakdownItem]:
    result = await get_spender_breakdown(
        db,
        space_id,
        period=period,
        month=month,
        category_id=category,
        merchant=merchant,
        tag=tag,
        payment_method_id=payment_method,
    )
    return [SpenderBreakdownItem(**item) for item in result]


@router.get("/limit-progress", response_model=list[LimitResponse])
async def limit_progress_endpoint(
    space_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[LimitResponse]:
    """All limits with current progress — delegates to limit service."""
    limits = await list_limits_with_progress(db, space_id)
    return [LimitResponse(**lim) for lim in limits]
