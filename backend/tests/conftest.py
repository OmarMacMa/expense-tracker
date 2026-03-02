import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings
from app.models import User
from app.schemas.space import SpaceCreate
from app.services.space import create_space


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional DB session that rolls back after each test."""
    engine = create_async_engine(settings.DATABASE_URL)

    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        # Override commit to use flush (so data is visible but not persisted)
        async def flush_instead_of_commit() -> None:
            await session.flush()

        session.commit = flush_instead_of_commit  # type: ignore[method-assign]

        yield session

        await session.close()
        await trans.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        google_id=f"google_{uuid.uuid4().hex[:12]}",
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Test User",
        avatar_url=None,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def test_space(db_session: AsyncSession, test_user: User):
    """Create a test space with the test_user as creator."""
    data = SpaceCreate(name="Test Space", currency_code="USD", timezone="UTC")
    return await create_space(db_session, test_user, data)


@pytest_asyncio.fixture
async def second_user(db_session: AsyncSession) -> User:
    """Create a second test user."""
    user = User(
        google_id=f"google_{uuid.uuid4().hex[:12]}",
        email=f"test2_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Second User",
        avatar_url=None,
    )
    db_session.add(user)
    await db_session.flush()
    return user
