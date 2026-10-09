import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import Category, Expense, ExpenseLine, Space, Tag, User
from app.models.expense import expense_line_tags
from app.services.time_window import Timeframe, TimeWindowResolver


def _escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE special characters."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


PERIOD_LABELS = {
    "this_week": "This Week",
    "last_week": "Last Week",
    "this_month": "This Month",
    "last_month": "Last Month",
    "ytd": "Year to Date",
}


def _resolve_timeframe(period: str | None) -> Timeframe:
    """Map period string to TimeWindowResolver timeframe."""
    if period in ("this_week", "last_week"):
        return "weekly"
    elif period in ("ytd",):
        return "yearly"
    return "monthly"  # default


def _average_period_count(timeframe: Timeframe) -> int:
    """Bound the lookback to nine weeks or three other calendar periods."""
    return 9 if timeframe == "weekly" else 3


def _resolve_ref_date(
    period: str | None,
    month: str | None,
    resolver: TimeWindowResolver,
) -> datetime | None:
    """Determine reference date from period/month params."""
    if period == "last_week":
        return resolver.get_previous_windows(
            "weekly", count=1, ref_date=datetime.now(UTC)
        )[0][0]
    elif period == "last_month":
        now = datetime.now(UTC)
        if now.month == 1:
            return now.replace(year=now.year - 1, month=12, day=15)
        return now.replace(month=now.month - 1, day=15)
    elif month:
        try:
            year, m = month.split("-")
            return datetime(int(year), int(m), 15, tzinfo=UTC)
        except (ValueError, IndexError):
            pass
    return datetime.now(UTC)


def _base_expense_query(space_id, start_utc, end_utc):
    """Base query for confirmed expenses in a time window."""
    return select(Expense).where(
        Expense.space_id == space_id,
        Expense.status == "confirmed",
        Expense.purchase_datetime >= start_utc,
        Expense.purchase_datetime <= end_utc,
    )


def _expense_conditions(
    space_id: uuid.UUID,
    start_utc: datetime,
    end_utc: datetime,
    spender_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    merchant: str | None = None,
    tag: str | None = None,
    payment_method_id: uuid.UUID | None = None,
) -> list[ColumnElement[bool]]:
    """Shared confirmed, space-scoped window and matching-expense filters."""
    conditions = [
        Expense.space_id == space_id,
        Expense.status == "confirmed",
        Expense.purchase_datetime >= start_utc,
        Expense.purchase_datetime <= end_utc,
        Expense.purchase_datetime <= datetime.now(UTC),
    ]
    if spender_id:
        conditions.append(Expense.spender_id == spender_id)
    if payment_method_id:
        conditions.append(Expense.payment_method_id == payment_method_id)
    if merchant:
        conditions.append(
            Expense.merchant_normalized.ilike(
                f"%{_escape_like(merchant.lower())}%", escape="\\"
            )
        )
    if category_id:
        conditions.append(
            Expense.id.in_(
                select(ExpenseLine.expense_id).where(
                    ExpenseLine.category_id == category_id
                )
            )
        )
    if tag:
        tag_norm = tag.strip().lower().lstrip("#")
        conditions.append(
            Expense.id.in_(
                select(ExpenseLine.expense_id)
                .join(
                    expense_line_tags,
                    ExpenseLine.id == expense_line_tags.c.expense_line_id,
                )
                .join(Tag, expense_line_tags.c.tag_id == Tag.id)
                .where(Tag.name == tag_norm)
            )
        )
    return conditions


async def _sum_expenses_in_window(
    db: AsyncSession,
    space_id: uuid.UUID,
    start_utc: datetime,
    end_utc: datetime,
    **filters,
) -> Decimal:
    """Sum confirmed matching expenses using the same filters as the trend."""
    stmt = select(func.coalesce(func.sum(Expense.total_amount), Decimal("0"))).where(
        *_expense_conditions(space_id, start_utc, end_utc, **filters)
    )
    result = await db.execute(stmt)
    return result.scalar_one() or Decimal("0")


async def _expense_amounts(
    db: AsyncSession,
    space_id: uuid.UUID,
    start_utc: datetime,
    end_utc: datetime,
    **filters,
) -> list[tuple[datetime, Decimal]]:
    """Fetch only dates and amounts for a bounded matching-expense range."""
    result = await db.execute(
        select(Expense.purchase_datetime, Expense.total_amount).where(
            *_expense_conditions(space_id, start_utc, end_utc, **filters)
        )
    )
    return [(dt, amount) for dt, amount in result.all()]


async def _historical_dailies(
    db: AsyncSession,
    space_id: uuid.UUID,
    resolver: TimeWindowResolver,
    timeframe: Timeframe,
    ref_date: datetime | None,
    **filters,
) -> list[dict[int, Decimal]]:
    """Fetch history once; exclude only zero-total weeks within nine windows."""
    windows = resolver.get_previous_windows(
        timeframe, count=_average_period_count(timeframe), ref_date=ref_date
    )
    rows = await _expense_amounts(
        db, space_id, windows[-1][0], windows[0][1], **filters
    )
    dailies: list[dict[int, Decimal]] = [defaultdict(Decimal) for _ in windows]
    for dt, amount in rows:
        for index, (start, end) in enumerate(windows):
            if start <= dt <= end:
                dailies[index][resolver.get_day_of_period(dt, timeframe)] += amount
                break
    if timeframe == "weekly":
        return [daily for daily in dailies if sum(daily.values()) != 0]
    return dailies


async def get_summary(
    db: AsyncSession,
    space_id: uuid.UUID,
    period: str | None = None,
    month: str | None = None,
    spender_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    merchant: str | None = None,
    tag: str | None = None,
    payment_method_id: uuid.UUID | None = None,
) -> dict:
    """Hero total + delta vs contributing weeks or three other prior periods."""
    space = await db.get(Space, space_id)
    resolver = TimeWindowResolver(space.timezone)
    timeframe = _resolve_timeframe(period)
    ref_date = _resolve_ref_date(period, month, resolver)

    start_utc, end_utc = resolver.get_current_window(timeframe, ref_date)

    filter_kwargs = dict(
        spender_id=spender_id,
        category_id=category_id,
        merchant=merchant,
        tag=tag,
        payment_method_id=payment_method_id,
    )

    total = await _sum_expenses_in_window(
        db, space_id, start_utc, end_utc, **filter_kwargs
    )

    if timeframe == "yearly":
        # Keep yearly summaries aggregated in SQL rather than fetching years of rows.
        prev_totals = [
            await _sum_expenses_in_window(db, space_id, p_start, p_end, **filter_kwargs)
            for p_start, p_end in resolver.get_previous_windows(
                timeframe, count=3, ref_date=ref_date
            )
        ]
    else:
        history = await _historical_dailies(
            db, space_id, resolver, timeframe, ref_date, **filter_kwargs
        )
        prev_totals = [sum(daily.values(), Decimal("0")) for daily in history]

    delta_pct = None
    if prev_totals:
        avg = sum(prev_totals) / len(prev_totals)
        if avg > 0:
            delta_pct = round(((total - avg) / avg) * 100, 1)

    label = PERIOD_LABELS.get(period or "this_month", period or "This Month")

    return {
        "total_spent": total,
        "delta_pct": delta_pct,
        "average_period_count": len(prev_totals),
        "period_label": label,
        "window_start": start_utc,
        "window_end": end_utc,
    }


async def get_spending_trend(
    db: AsyncSession,
    space_id: uuid.UUID,
    period: str | None = None,
    month: str | None = None,
    spender_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    merchant: str | None = None,
    tag: str | None = None,
    payment_method_id: uuid.UUID | None = None,
) -> dict:
    """Cumulative spend vs contributing weeks or three prior non-yearly periods."""
    space = await db.get(Space, space_id)
    resolver = TimeWindowResolver(space.timezone)
    timeframe = _resolve_timeframe(period)
    ref_date = _resolve_ref_date(period, month, resolver)

    start_utc, end_utc = resolver.get_current_window(timeframe, ref_date)

    # Compute the total days in this period for the current series
    period_days = resolver.get_day_of_period(end_utc, timeframe)

    current_daily = await _daily_amounts(
        db,
        space_id,
        start_utc,
        end_utc,
        resolver,
        timeframe,
        spender_id=spender_id,
        category_id=category_id,
        merchant=merchant,
        tag=tag,
        payment_method_id=payment_method_id,
    )
    current_series = _to_cumulative(current_daily, period_days=period_days)

    # Previous windows for average (skip for yearly — too expensive and not useful)
    avg_series: dict[int, Decimal] = {}
    average_period_count = 0
    if timeframe != "yearly":
        history = await _historical_dailies(
            db,
            space_id,
            resolver,
            timeframe,
            ref_date,
            spender_id=spender_id,
            category_id=category_id,
            merchant=merchant,
            tag=tag,
            payment_method_id=payment_method_id,
        )
        average_period_count = len(history)
        all_prev_dailies = [
            _to_cumulative(daily, period_days=period_days) for daily in history
        ]
        avg_series = _average_series(all_prev_dailies)

    now_utc = datetime.now(UTC)
    current_day = (
        resolver.get_day_of_period(now_utc, timeframe)
        if start_utc <= now_utc <= end_utc
        else None
    )

    return {
        "current_series": [
            {"day": d, "cumulative": v} for d, v in current_series.items()
        ],
        "average_series": [{"day": d, "cumulative": v} for d, v in avg_series.items()],
        "average_period_count": average_period_count,
        "timeframe": timeframe,
        "year": resolver.localize_for_display(start_utc).year,
        "current_day": current_day,
    }


async def _daily_amounts(
    db: AsyncSession,
    space_id: uuid.UUID,
    start_utc: datetime,
    end_utc: datetime,
    resolver: TimeWindowResolver,
    timeframe: Timeframe,
    **filters,
) -> dict[int, Decimal]:
    """Get daily amounts grouped by day-of-period."""
    rows = await _expense_amounts(db, space_id, start_utc, end_utc, **filters)

    daily: dict[int, Decimal] = defaultdict(Decimal)
    for dt, amount in rows:
        day = resolver.get_day_of_period(dt, timeframe)
        daily[day] += amount

    return dict(daily)


def _to_cumulative(
    daily: dict[int, Decimal], period_days: int | None = None
) -> dict[int, Decimal]:
    """Convert daily amounts to cumulative series (1-based days).

    If period_days is given, the series extends to cover the full period
    even if no expenses exist on later days.
    """
    if not daily and period_days is None:
        return {}
    max_day = max(daily.keys()) if daily else 0
    if period_days is not None:
        max_day = period_days
    if max_day < 1:
        return {}
    cumulative = {}
    running = Decimal("0")
    for day in range(1, max_day + 1):
        running += daily.get(day, Decimal("0"))
        cumulative[day] = running
    return cumulative


def _average_series(
    all_series: list[dict[int, Decimal]],
) -> dict[int, Decimal]:
    """Average multiple cumulative series by day index.

    Each series is expected to be cumulative (non-decreasing). If a series
    is shorter than others, missing trailing days are filled by carrying
    forward its last known value. This guarantees the average never
    decreases even if a caller passes un-normalized series.
    """
    if not all_series:
        return {}

    # Determine the full day range across all series
    all_days: set[int] = set()
    for series in all_series:
        all_days.update(series.keys())
    if not all_days:
        return {}

    min_day = min(all_days)
    max_day = max(all_days)
    n = len(all_series)

    # Build a dense value per (series, day), carrying forward last known value
    combined: dict[int, list[Decimal]] = defaultdict(list)
    for series in all_series:
        last_value = Decimal("0")
        for day in range(min_day, max_day + 1):
            if day in series:
                last_value = series[day]
            combined[day].append(last_value)

    return {day: sum(values) / n for day, values in sorted(combined.items())}


async def get_category_breakdown(
    db: AsyncSession,
    space_id: uuid.UUID,
    period: str | None = None,
    month: str | None = None,
    spender_id: uuid.UUID | None = None,
    merchant: str | None = None,
    tag: str | None = None,
    payment_method_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
) -> list[dict]:
    """Category totals within window."""
    space = await db.get(Space, space_id)
    resolver = TimeWindowResolver(space.timezone)
    timeframe = _resolve_timeframe(period)
    ref_date = _resolve_ref_date(period, month, resolver)
    start_utc, end_utc = resolver.get_current_window(timeframe, ref_date)

    stmt = (
        select(
            ExpenseLine.category_id,
            Category.name,
            func.sum(ExpenseLine.amount).label("total"),
        )
        .join(Expense, ExpenseLine.expense_id == Expense.id)
        .join(Category, ExpenseLine.category_id == Category.id)
        .where(
            Expense.space_id == space_id,
            Expense.status == "confirmed",
            Expense.purchase_datetime >= start_utc,
            Expense.purchase_datetime <= end_utc,
        )
        .group_by(ExpenseLine.category_id, Category.name)
        .order_by(func.sum(ExpenseLine.amount).desc())
    )
    if spender_id:
        stmt = stmt.where(Expense.spender_id == spender_id)
    if category_id:
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id).where(
                    ExpenseLine.category_id == category_id
                )
            )
        )
    if merchant:
        stmt = stmt.where(
            Expense.merchant_normalized.ilike(
                f"%{_escape_like(merchant.lower())}%", escape="\\"
            )
        )
    if payment_method_id:
        stmt = stmt.where(Expense.payment_method_id == payment_method_id)
    if tag:
        tag_norm = tag.strip().lower().lstrip("#")
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id)
                .join(
                    expense_line_tags,
                    ExpenseLine.id == expense_line_tags.c.expense_line_id,
                )
                .join(Tag, expense_line_tags.c.tag_id == Tag.id)
                .where(Tag.name == tag_norm)
            )
        )

    result = await db.execute(stmt)
    rows = result.all()

    grand_total = sum(r.total for r in rows) if rows else Decimal("1")
    return [
        {
            "category_id": r.category_id,
            "category_name": r.name,
            "total": r.total,
            "percentage": (
                round((r.total / grand_total) * 100, 1)
                if grand_total > 0
                else Decimal("0")
            ),
        }
        for r in rows
    ]


async def get_merchant_leaderboard(
    db: AsyncSession,
    space_id: uuid.UUID,
    period: str | None = None,
    month: str | None = None,
    spender_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    tag: str | None = None,
    payment_method_id: uuid.UUID | None = None,
    merchant: str | None = None,
) -> list[dict]:
    """Top merchants by amount in window."""
    space = await db.get(Space, space_id)
    resolver = TimeWindowResolver(space.timezone)
    timeframe = _resolve_timeframe(period)
    ref_date = _resolve_ref_date(period, month, resolver)
    start_utc, end_utc = resolver.get_current_window(timeframe, ref_date)

    stmt = (
        select(
            Expense.merchant,
            func.sum(Expense.total_amount).label("total"),
            func.count(Expense.id).label("count"),
        )
        .where(
            Expense.space_id == space_id,
            Expense.status == "confirmed",
            Expense.purchase_datetime >= start_utc,
            Expense.purchase_datetime <= end_utc,
        )
        .group_by(Expense.merchant)
        .order_by(func.sum(Expense.total_amount).desc())
        .limit(10)
    )
    if spender_id:
        stmt = stmt.where(Expense.spender_id == spender_id)
    if merchant:
        stmt = stmt.where(
            Expense.merchant_normalized.ilike(
                f"%{_escape_like(merchant.lower())}%", escape="\\"
            )
        )
    if payment_method_id:
        stmt = stmt.where(Expense.payment_method_id == payment_method_id)
    if category_id:
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id).where(
                    ExpenseLine.category_id == category_id
                )
            )
        )
    if tag:
        tag_norm = tag.strip().lower().lstrip("#")
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id)
                .join(
                    expense_line_tags,
                    ExpenseLine.id == expense_line_tags.c.expense_line_id,
                )
                .join(Tag, expense_line_tags.c.tag_id == Tag.id)
                .where(Tag.name == tag_norm)
            )
        )

    result = await db.execute(stmt)
    rows = result.all()

    return [{"merchant": r.merchant, "total": r.total, "count": r.count} for r in rows]


async def get_spender_breakdown(
    db: AsyncSession,
    space_id: uuid.UUID,
    period: str | None = None,
    month: str | None = None,
    category_id: uuid.UUID | None = None,
    merchant: str | None = None,
    tag: str | None = None,
    payment_method_id: uuid.UUID | None = None,
    spender_id: uuid.UUID | None = None,
) -> list[dict]:
    """Totals per spender in window."""
    space = await db.get(Space, space_id)
    resolver = TimeWindowResolver(space.timezone)
    timeframe = _resolve_timeframe(period)
    ref_date = _resolve_ref_date(period, month, resolver)
    start_utc, end_utc = resolver.get_current_window(timeframe, ref_date)

    stmt = (
        select(
            Expense.spender_id,
            User.display_name,
            func.sum(Expense.total_amount).label("total"),
        )
        .join(User, Expense.spender_id == User.id)
        .where(
            Expense.space_id == space_id,
            Expense.status == "confirmed",
            Expense.purchase_datetime >= start_utc,
            Expense.purchase_datetime <= end_utc,
        )
        .group_by(Expense.spender_id, User.display_name)
        .order_by(func.sum(Expense.total_amount).desc())
    )
    if merchant:
        stmt = stmt.where(
            Expense.merchant_normalized.ilike(
                f"%{_escape_like(merchant.lower())}%", escape="\\"
            )
        )
    if spender_id:
        stmt = stmt.where(Expense.spender_id == spender_id)
    if payment_method_id:
        stmt = stmt.where(Expense.payment_method_id == payment_method_id)
    if category_id:
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id).where(
                    ExpenseLine.category_id == category_id
                )
            )
        )
    if tag:
        tag_norm = tag.strip().lower().lstrip("#")
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id)
                .join(
                    expense_line_tags,
                    ExpenseLine.id == expense_line_tags.c.expense_line_id,
                )
                .join(Tag, expense_line_tags.c.tag_id == Tag.id)
                .where(Tag.name == tag_norm)
            )
        )

    result = await db.execute(stmt)
    rows = result.all()

    grand_total = sum(r.total for r in rows) if rows else Decimal("1")
    return [
        {
            "spender_id": r.spender_id,
            "display_name": r.display_name,
            "total": r.total,
            "percentage": (
                round((r.total / grand_total) * 100, 1)
                if grand_total > 0
                else Decimal("0")
            ),
        }
        for r in rows
    ]
