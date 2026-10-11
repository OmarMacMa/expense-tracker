from decimal import Decimal

from sqlalchemy import Numeric, literal
from sqlalchemy.sql.elements import ColumnElement

from app.models import Expense
from app.schemas.amount_range import AmountRange


def amount_range_predicates(
    min_amount: Decimal | None = None,
    max_amount: Decimal | None = None,
) -> tuple[ColumnElement[bool], ...]:
    """Inclusive expense-total predicates, never line amounts or budget limits."""
    bounds = AmountRange(min_amount=min_amount, max_amount=max_amount)
    predicates: list[ColumnElement[bool]] = []
    # Column-typed binds would round bounds to NUMERIC(12, 2) before comparing.
    if bounds.min_amount is not None:
        predicates.append(
            Expense.total_amount >= literal(bounds.min_amount, type_=Numeric())
        )
    if bounds.max_amount is not None:
        predicates.append(
            Expense.total_amount <= literal(bounds.max_amount, type_=Numeric())
        )
    return tuple(predicates)
