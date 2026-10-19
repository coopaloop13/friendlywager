from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings


@lru_cache
def sessionmaker() -> async_sessionmaker[AsyncSession]:
    # lazy so importing app.db needs no env; engine connects on first use
    return async_sessionmaker(create_async_engine(Settings().database_url), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as session:
        yield session
