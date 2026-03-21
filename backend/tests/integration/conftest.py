import uuid
from collections.abc import AsyncGenerator
from types import SimpleNamespace

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.jwt import create_access_token
from app.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Category, PaymentMethod, Space, SpaceMember, User


@pytest_asyncio.fixture
async def test_engine():
    """Per-test async engine bound to the current event loop.

    Overrides the app's get_db so the ASGI app uses connections
    from the same event loop as the test.
    """
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield engine, factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def test_user_with_space(test_engine):
    """Create a user with a space and return data dict."""
    _engine, factory = test_engine

    async with factory() as session:
        user = User(
            google_id=f"google_{uuid.uuid4().hex[:12]}",
            email=f"integration_{uuid.uuid4().hex[:8]}@test.com",
            display_name="Integration User",
        )
        session.add(user)
        await session.flush()

        space = Space(
            name=f"Test Space {uuid.uuid4().hex[:6]}",
            currency_code="USD",
            timezone="UTC",
        )
        session.add(space)
        await session.flush()

        member = SpaceMember(space_id=space.id, user_id=user.id)
        session.add(member)

        uncat = Category(
            space_id=space.id,
            name="Uncategorized",
            normalized_name="uncategorized",
            is_system=True,
        )
        session.add(uncat)
        cash = PaymentMethod(
            space_id=space.id,
            label="Cash",
            is_system=True,
            owner_id=None,
        )
        session.add(cash)

        await session.commit()
        await session.refresh(user)
        await session.refresh(space)
        await session.refresh(uncat)

        data = {
            "user": SimpleNamespace(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
            ),
            "space": SimpleNamespace(id=space.id, name=space.name),
            "category_id": uncat.id,
            "token": create_access_token(user.id),
        }

    return data


@pytest_asyncio.fixture
async def auth_client(test_user_with_space) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client with auth cookie set."""
    token = test_user_with_space["token"]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={"access_token": token},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def unauth_client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client WITHOUT auth cookie."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
