import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PaymentMethod


async def list_payment_methods(
    db: AsyncSession, space_id: uuid.UUID
) -> Sequence[PaymentMethod]:
    """List all payment methods in a space."""
    stmt = (
        select(PaymentMethod)
        .where(PaymentMethod.space_id == space_id)
        .order_by(PaymentMethod.created_at)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def create_payment_method(
    db: AsyncSession, space_id: uuid.UUID, user_id: uuid.UUID, data
) -> PaymentMethod:
    """Create a payment method owned by the current user."""
    pm = PaymentMethod(
        space_id=space_id,
        owner_id=user_id,
        label=data.label,
        is_system=False,
    )
    db.add(pm)
    await db.commit()
    await db.refresh(pm)
    return pm


async def update_payment_method(
    db: AsyncSession,
    space_id: uuid.UUID,
    method_id: uuid.UUID,
    user_id: uuid.UUID,
    data,
) -> PaymentMethod:
    """Update a payment method. Owner only. System methods cannot be updated."""
    pm = await _get_payment_method(db, space_id, method_id)

    if pm.is_system:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "SYSTEM_ENTITY",
                    "message": "Cannot update system payment method",
                }
            },
        )

    if pm.owner_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Only the owner can update this payment method",
                }
            },
        )

    if data.label is not None:
        pm.label = data.label

    await db.commit()
    await db.refresh(pm)
    return pm


async def delete_payment_method(
    db: AsyncSession,
    space_id: uuid.UUID,
    method_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete a payment method. Owner only. System methods cannot be deleted."""
    pm = await _get_payment_method(db, space_id, method_id)

    if pm.is_system:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "SYSTEM_ENTITY",
                    "message": "Cannot delete system payment method",
                }
            },
        )

    if pm.owner_id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Only the owner can delete this payment method",
                }
            },
        )

    await db.delete(pm)
    await db.commit()


async def _get_payment_method(
    db: AsyncSession, space_id: uuid.UUID, method_id: uuid.UUID
) -> PaymentMethod:
    """Get payment method by ID within space. Raises 404 if not found."""
    stmt = select(PaymentMethod).where(
        PaymentMethod.space_id == space_id,
        PaymentMethod.id == method_id,
    )
    result = await db.execute(stmt)
    pm = result.scalar_one_or_none()
    if pm is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Payment method not found",
                }
            },
        )
    return pm
