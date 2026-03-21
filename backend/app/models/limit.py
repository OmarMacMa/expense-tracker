import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Limit(Base):
    __tablename__ = "limits"
    __table_args__ = (
        CheckConstraint(
            "timeframe IN ('weekly', 'monthly', 'quarterly', 'yearly')",
            name="ck_limits_timeframe",
        ),
        CheckConstraint(
            "threshold_amount >= 0.01 AND threshold_amount <= 999999.99",
            name="ck_limits_threshold_amount",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    warning_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.6000")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    filters: Mapped[list["LimitFilter"]] = relationship(
        back_populates="limit", cascade="all, delete-orphan"
    )


class LimitFilter(Base):
    __tablename__ = "limit_filters"
    __table_args__ = (
        CheckConstraint(
            "filter_type IN ("
            "'category', 'merchant', 'tag', "
            "'spender', 'beneficiary', 'payment_method')",
            name="ck_limit_filters_filter_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    limit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("limits.id", ondelete="CASCADE"),
        nullable=False,
    )
    filter_type: Mapped[str] = mapped_column(Text, nullable=False)
    filter_value: Mapped[str] = mapped_column(Text, nullable=False)

    limit: Mapped["Limit"] = relationship(back_populates="filters")
