import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from src.config.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine = create_async_engine(
    "mysql+asyncmy://{user}:{passwd}@{host}:{port}/{db}?charset=utf8mb4".format(
        user=settings.db_user,
        passwd=settings.db_pass,
        host=settings.db_host,
        port=settings.db_port,
        db=settings.db_name,
    ),
    pool_size=10,
    max_overflow=10,
    echo=True,
    pool_pre_ping=True,
    pool_timeout=600,
)

_async_sessionmaker = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    `session: AsyncSession = Depends(get_session)`로 사용
    생성된 connection pool 중 하나를 할당 받아 사용
    """
    session = _async_sessionmaker()
    async with session() as session:
        yield session
