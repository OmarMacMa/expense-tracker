from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class AmountRange(BaseModel):
    min_amount: Decimal | None = Field(None, ge=0, allow_inf_nan=False)
    max_amount: Decimal | None = Field(None, ge=0, allow_inf_nan=False)

    @field_validator("min_amount", "max_amount", mode="before")
    @classmethod
    def blank_is_unbounded(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def ordered_bounds(self) -> "AmountRange":
        if (
            self.min_amount is not None
            and self.max_amount is not None
            and self.min_amount > self.max_amount
        ):
            raise ValueError("Minimum amount must not exceed maximum amount")
        return self
