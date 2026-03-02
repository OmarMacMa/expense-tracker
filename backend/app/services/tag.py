import re
import uuid
from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tag

TAG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def normalize_tag_name(name: str) -> str:
    """Normalize: lowercase, trim, remove # prefix."""
    name = name.strip().lstrip("#").strip()
    return name.lower()


async def list_tags(db: AsyncSession, space_id: uuid.UUID) -> Sequence[Tag]:
    """List all tags in a space, ordered by name."""
    stmt = select(Tag).where(Tag.space_id == space_id).order_by(Tag.name)
    result = await db.execute(stmt)
    return result.scalars().all()


async def ensure_tags(
    db: AsyncSession, space_id: uuid.UUID, tag_names: list[str]
) -> list[Tag]:
    """Normalize tag names, create any that don't exist, return all Tag objects.

    Used by expense creation in Phase 6.
    Validates tag names match allowed pattern.
    """
    if not tag_names:
        return []

    tags = []
    for raw_name in tag_names:
        normalized = normalize_tag_name(raw_name)
        if not normalized:
            continue
        if not TAG_PATTERN.match(normalized):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "INVALID_TAG",
                        "message": (
                            f"Invalid tag name: {raw_name}. "
                            "Allowed: alphanumeric, hyphens, underscores."
                        ),
                    }
                },
            )

        # Find or create
        stmt = select(Tag).where(Tag.space_id == space_id, Tag.name == normalized)
        result = await db.execute(stmt)
        tag = result.scalar_one_or_none()

        if tag is None:
            tag = Tag(space_id=space_id, name=normalized)
            db.add(tag)
            await db.flush()

        tags.append(tag)

    return tags
