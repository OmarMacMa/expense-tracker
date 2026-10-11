from fastapi import Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.schemas.amount_range import AmountRange


def get_amount_range(
    min_amount: str | None = Query(None),
    max_amount: str | None = Query(None),
) -> AmountRange:
    """Parse decimal query strings without a floating-point conversion."""
    try:
        return AmountRange(min_amount=min_amount, max_amount=max_amount)
    except ValidationError as error:
        raise RequestValidationError(
            [{**item, "loc": ("query", *item["loc"])} for item in error.errors()]
        ) from error
