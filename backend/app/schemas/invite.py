import uuid
from datetime import datetime

from pydantic import BaseModel


class InviteResponse(BaseModel):
    id: uuid.UUID
    token: str
    space_id: uuid.UUID
    expires_at: datetime
    used_at: datetime | None
    created_by: uuid.UUID

    model_config = {"from_attributes": True}


class JoinResponse(BaseModel):
    space_id: uuid.UUID
    space_name: str
    message: str


class InvitePreviewResponse(BaseModel):
    """Public preview of an invite for the user-facing confirmation step.

    Returns the target space's display info without consuming the invite,
    so the frontend can render "You're about to join <space_name>" before
    the user commits. Auth still required (we don't expose space names to
    arbitrary visitors), but works for users with or without their own space.
    """

    space_id: uuid.UUID
    space_name: str
    space_currency_code: str
