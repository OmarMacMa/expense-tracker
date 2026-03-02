import pytest

from app.services.tag import ensure_tags, list_tags


@pytest.mark.asyncio
async def test_list_tags_empty(db_session, test_user, test_space):
    tags = await list_tags(db_session, test_space.id)
    assert len(tags) == 0


@pytest.mark.asyncio
async def test_ensure_tags_creates_new(db_session, test_user, test_space):
    tags = await ensure_tags(db_session, test_space.id, ["groceries", "weekly"])
    assert len(tags) == 2
    names = {t.name for t in tags}
    assert names == {"groceries", "weekly"}


@pytest.mark.asyncio
async def test_ensure_tags_returns_existing(db_session, test_user, test_space):
    await ensure_tags(db_session, test_space.id, ["groceries"])
    tags = await ensure_tags(db_session, test_space.id, ["groceries", "weekly"])
    assert len(tags) == 2
    # Should not create duplicate
    all_tags = await list_tags(db_session, test_space.id)
    assert len(all_tags) == 2


@pytest.mark.asyncio
async def test_ensure_tags_normalizes(db_session, test_user, test_space):
    tags = await ensure_tags(db_session, test_space.id, ["#Groceries", "  WEEKLY  "])
    names = {t.name for t in tags}
    assert names == {"groceries", "weekly"}
