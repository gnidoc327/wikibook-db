import logging

import redis.asyncio as aioredis

from ch05.config.config import settings

logger = logging.getLogger(__name__)

_pool = aioredis.ConnectionPool(
    host=settings.valkey.host,
    port=settings.valkey.port,
    password=settings.valkey.passwd,
    max_connections=10,
    decode_responses=True,
)

_client = aioredis.Redis(connection_pool=_pool)


def get_client() -> aioredis.Redis:
    """
    `client: Redis = Depends(get_client)`로 사용
    """
    return _client
