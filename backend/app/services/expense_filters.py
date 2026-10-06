"""Shared, space-scoped predicates for exploratory expense filters."""

import uuid
from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import Select, or_, select

from app.models import Category, Expense, ExpenseLine, Tag
from app.models.expense import expense_line_tags

T = TypeVar("T", str, uuid.UUID)
UUIDFilter = uuid.UUID | Sequence[uuid.UUID] | None
TextFilter = str | Sequence[str] | None


def filter_values(value: T | Sequence[T] | None) -> list[T]:
    """Keep scalar service callers compatible and deduplicate selections."""
    if value is None:
        return []
    values = [value] if isinstance(value, str | uuid.UUID) else value
    return list(dict.fromkeys(values))


def escape_like(value: str) -> str:
    """Treat merchant names as literals, not SQL wildcard expressions."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def apply_expense_filters(
    stmt: Select,
    space_id: uuid.UUID,
    *,
    spender_id: UUIDFilter = None,
    category_id: UUIDFilter = None,
    merchant: TextFilter = None,
    tag: TextFilter = None,
    payment_method_id: UUIDFilter = None,
) -> Select:
    """AND dimensions, OR selections; subqueries never multiply expenses."""
    spenders = filter_values(spender_id)
    categories = filter_values(category_id)
    methods = filter_values(payment_method_id)
    merchants = [name for name in filter_values(merchant) if name]
    tags = list(
        dict.fromkeys(
            name.strip().lower().lstrip("#")
            for name in filter_values(tag)
            if name.strip().lstrip("#")
        )
    )
    stmt = stmt.where(Expense.space_id == space_id)
    if spenders:
        stmt = stmt.where(Expense.spender_id.in_(spenders))
    if methods:
        stmt = stmt.where(Expense.payment_method_id.in_(methods))
    if merchants:
        stmt = stmt.where(
            or_(
                *(
                    Expense.merchant_normalized.ilike(
                        f"%{escape_like(name.lower())}%", escape="\\"
                    )
                    for name in merchants
                )
            )
        )
    if categories:
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id)
                .join(Category, ExpenseLine.category_id == Category.id)
                .where(Category.space_id == space_id, Category.id.in_(categories))
            )
        )
    if tags:
        stmt = stmt.where(
            Expense.id.in_(
                select(ExpenseLine.expense_id)
                .join(
                    expense_line_tags,
                    ExpenseLine.id == expense_line_tags.c.expense_line_id,
                )
                .join(Tag, expense_line_tags.c.tag_id == Tag.id)
                .where(Tag.space_id == space_id, Tag.name.in_(tags))
            )
        )
    return stmt
