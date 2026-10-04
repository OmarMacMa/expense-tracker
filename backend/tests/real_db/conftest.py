from collections.abc import AsyncGenerator

import pytest_asyncio

from tests.membership_support import MembershipDatabase


@pytest_asyncio.fixture
async def real_db() -> AsyncGenerator[MembershipDatabase, None]:
    async with MembershipDatabase() as database:
        yield database
