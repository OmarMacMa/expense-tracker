import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PaymentMethod, SpaceMember, User
from app.services.membership import lock_spaces, lock_user


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
    await lock_user(db, user_id)
    await lock_spaces(db, [space_id])
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

    if not await can_manage(db, pm, user_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Only the current owner or remaining members "
                    "of a departed owner can update this method",
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
    await lock_user(db, user_id)
    await lock_spaces(db, [space_id])
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

    if not await can_manage(db, pm, user_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "Only the current owner or remaining members "
                    "of a departed owner can delete this method",
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


async def can_manage(db: AsyncSession, pm: PaymentMethod, user_id: uuid.UUID) -> bool:
    """Require live membership; inherit management only when the owner has left."""
    member_ids = set(
        await db.scalars(
            select(SpaceMember.user_id).where(SpaceMember.space_id == pm.space_id)
        )
    )
    return _can_manage(pm, user_id, member_ids)


def _can_manage(
    pm: PaymentMethod, user_id: uuid.UUID, member_ids: set[uuid.UUID]
) -> bool:
    return (
        not pm.is_system
        and user_id in member_ids
        and (pm.owner_id == user_id or pm.owner_id not in member_ids)
    )


async def payment_method_response(
    db: AsyncSession, pm: PaymentMethod, user_id: uuid.UUID
) -> dict:
    """Provide authoritative permissions and historical attribution to clients."""
    return (await payment_method_responses(db, [pm], user_id))[0]


async def payment_method_responses(
    db: AsyncSession, methods: Sequence[PaymentMethod], user_id: uuid.UUID
) -> list[dict]:
    """Batch owner and membership metadata without per-method database reads."""
    if not methods:
        return []
    space_ids = {method.space_id for method in methods}
    owner_ids = {method.owner_id for method in methods if method.owner_id is not None}
    owner_names = dict(
        (
            await db.execute(
                select(User.id, User.display_name).where(User.id.in_(owner_ids))
            )
        ).all()
    )
    members_by_space: dict[uuid.UUID, set[uuid.UUID]] = {
        space_id: set() for space_id in space_ids
    }
    member_rows = await db.execute(
        select(SpaceMember.space_id, SpaceMember.user_id).where(
            SpaceMember.space_id.in_(space_ids)
        )
    )
    for space_id, member_id in member_rows:
        members_by_space[space_id].add(member_id)
    return [
        {
            "id": pm.id,
            "label": pm.label,
            "is_system": pm.is_system,
            "owner_id": pm.owner_id,
            "created_at": pm.created_at,
            "owner_display_name": owner_names.get(pm.owner_id),
            "owner_is_member": pm.owner_id in members_by_space[pm.space_id],
            "can_manage": _can_manage(pm, user_id, members_by_space[pm.space_id]),
        }
        for pm in methods
    ]
