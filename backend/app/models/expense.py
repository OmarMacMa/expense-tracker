import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

expense_line_tags = Table(
    "expense_line_tags",
    Base.metadata,
    Column(
        "expense_line_id",
        UUID(as_uuid=True),
        ForeignKey("expense_lines.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id"),
        primary_key=True,
    ),
)


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint(
            "total_amount >= 0.01 AND total_amount <= 999999.99",
            name="ck_expenses_total_amount",
        ),
        CheckConstraint(
            "status IN ('confirmed', 'pending')",
            name="ck_expenses_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=False
    )
    merchant: Mapped[str] = mapped_column(Text, nullable=False)
    merchant_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    purchase_datetime: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    spender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    recurring_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recurring_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    lines: Mapped[list["ExpenseLine"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )
    spender: Mapped["User"] = relationship()


class ExpenseLine(Base):
    __tablename__ = "expense_lines"
    __table_args__ = (
        CheckConstraint(
            "amount >= 0.01 AND amount <= 999999.99",
            name="ck_expense_lines_amount",
        ),
        CheckConstraint(
            "beneficiary_type IN ('member', 'shared')",
            name="ck_expense_lines_beneficiary_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    beneficiary_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    beneficiary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    line_order: Mapped[int] = mapped_column(Integer, nullable=False)

    expense: Mapped["Expense"] = relationship(back_populates="lines")
    tags: Mapped[list["Tag"]] = relationship(secondary=expense_line_tags)
    category: Mapped["Category"] = relationship()


# Used as ExpenseLineTag in __init__.py exports
ExpenseLineTag = expense_line_tags

from app.models.category import Category  # noqa: E402, F401
from app.models.tag import Tag  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
