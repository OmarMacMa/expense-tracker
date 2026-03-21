import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class RecurringTemplate(Base):
    __tablename__ = "recurring_templates"
    __table_args__ = (
        CheckConstraint(
            "schedule IN ('weekly', 'monthly', 'quarterly', 'yearly')",
            name="ck_recurring_templates_schedule",
        ),
        CheckConstraint(
            "default_amount >= 0.01 AND default_amount <= 999999.99",
            name="ck_recurring_templates_default_amount",
        ),
        CheckConstraint(
            "default_beneficiary_type IN ('member', 'shared')",
            name="ck_recurring_templates_default_beneficiary_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    schedule: Mapped[str] = mapped_column(Text, nullable=False)
    default_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    default_merchant: Mapped[str] = mapped_column(Text, nullable=False)
    default_category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    default_spender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    default_beneficiary_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_beneficiary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    default_payment_method_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_methods.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_tags: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
