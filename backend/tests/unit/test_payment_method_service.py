import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import PaymentMethod
from app.schemas.payment_method import PaymentMethodCreate, PaymentMethodUpdate
from app.services.payment_method import (
    create_payment_method,
    delete_payment_method,
    update_payment_method,
)


@pytest.mark.asyncio
async def test_create_payment_method(db_session, test_user, test_space):
    data = PaymentMethodCreate(label="Visa")
    pm = await create_payment_method(db_session, test_space.id, test_user.id, data)
    assert pm.label == "Visa"
    assert pm.owner_id == test_user.id
    assert pm.is_system is False


@pytest.mark.asyncio
async def test_cannot_delete_cash(db_session, test_user, test_space):
    """Cash (is_system=True) cannot be deleted."""
    stmt = select(PaymentMethod).where(
        PaymentMethod.space_id == test_space.id,
        PaymentMethod.is_system == True,  # noqa: E712
    )
    result = await db_session.execute(stmt)
    cash = result.scalar_one()

    with pytest.raises(HTTPException) as exc_info:
        await delete_payment_method(db_session, test_space.id, cash.id, test_user.id)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_owner_only_delete(db_session, test_user, second_user, test_space):
    """Only the owner can delete a payment method."""
    data = PaymentMethodCreate(label="MyCard")
    pm = await create_payment_method(db_session, test_space.id, test_user.id, data)

    with pytest.raises(HTTPException) as exc_info:
        await delete_payment_method(db_session, test_space.id, pm.id, second_user.id)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_owner_only_update(db_session, test_user, second_user, test_space):
    """Only the owner can update a payment method."""
    data = PaymentMethodCreate(label="MyCard")
    pm = await create_payment_method(db_session, test_space.id, test_user.id, data)

    with pytest.raises(HTTPException) as exc_info:
        await update_payment_method(
            db_session,
            test_space.id,
            pm.id,
            second_user.id,
            PaymentMethodUpdate(label="NotMine"),
        )
    assert exc_info.value.status_code == 403
