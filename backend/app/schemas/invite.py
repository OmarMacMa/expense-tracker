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
