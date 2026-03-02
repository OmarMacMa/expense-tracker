import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.middleware.space import get_current_space_member
from app.models import SpaceMember, User
from app.schemas.payment_method import (
    PaymentMethodCreate,
    PaymentMethodResponse,
    PaymentMethodUpdate,
)
from app.services.payment_method import (
    create_payment_method,
    delete_payment_method,
    list_payment_methods,
    update_payment_method,
)

router = APIRouter(prefix="/api/v1/spaces/{space_id}", tags=["payment-methods"])


@router.get("/payment-methods", response_model=list[PaymentMethodResponse])
async def list_payment_methods_endpoint(
    space_id: uuid.UUID,
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentMethodResponse]:
    """List all payment methods in a space."""
    methods = await list_payment_methods(db, space_id)
    return [PaymentMethodResponse.model_validate(m) for m in methods]


@router.post("/payment-methods", response_model=PaymentMethodResponse, status_code=201)
async def create_payment_method_endpoint(
    space_id: uuid.UUID,
    data: PaymentMethodCreate,
    member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> PaymentMethodResponse:
    """Create a payment method owned by the current user."""
    pm = await create_payment_method(db, space_id, member.user_id, data)
    return PaymentMethodResponse.model_validate(pm)


@router.patch("/payment-methods/{method_id}", response_model=PaymentMethodResponse)
async def update_payment_method_endpoint(
    space_id: uuid.UUID,
    method_id: uuid.UUID,
    data: PaymentMethodUpdate,
    current_user: User = Depends(get_current_user),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> PaymentMethodResponse:
    """Update a payment method. Owner only."""
    pm = await update_payment_method(db, space_id, method_id, current_user.id, data)
    return PaymentMethodResponse.model_validate(pm)


@router.delete("/payment-methods/{method_id}", status_code=204)
async def delete_payment_method_endpoint(
    space_id: uuid.UUID,
    method_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    _member: SpaceMember = Depends(get_current_space_member),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a payment method. Owner only."""
    await delete_payment_method(db, space_id, method_id, current_user.id)
