from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.category import Category  # noqa: E402
from app.models.expense import Expense, ExpenseLine, ExpenseLineTag  # noqa: E402
from app.models.limit import Limit, LimitFilter  # noqa: E402
from app.models.merchant import Merchant  # noqa: E402
from app.models.monthly_wrap import MonthlyWrap  # noqa: E402
from app.models.payment_method import PaymentMethod  # noqa: E402
from app.models.recurring import RecurringTemplate  # noqa: E402
from app.models.space import InviteLink, Space, SpaceMember  # noqa: E402
from app.models.tag import Tag  # noqa: E402
from app.models.user import User  # noqa: E402

__all__ = [
    "Base",
    "User",
    "Space",
    "SpaceMember",
    "InviteLink",
    "Category",
    "PaymentMethod",
    "Merchant",
    "Tag",
    "RecurringTemplate",
    "Expense",
    "ExpenseLine",
    "ExpenseLineTag",
    "Limit",
    "LimitFilter",
    "MonthlyWrap",
]
