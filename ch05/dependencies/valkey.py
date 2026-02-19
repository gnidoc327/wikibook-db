import logging

import redis.asyncio as aioredis

from ch05.config.config import settings

logger = logging.getLogger(__name__)

# Valkey는 Redis 프로토콜 호환이므로 redis-py 클라이언트를 사용합니다.
# redis.asyncio의 ConnectionPool은 max_connections만 지원하고 min 설정은 없습니다.
# 커넥션은 요청 시 생성되고 max_connections까지 풀에 유지됩니다.
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


async def startup() -> None:
    """서버 시작 시 Valkey 연결을 확인합니다."""
    pong = await _client.ping()
    logger.info("Valkey 연결 완료: PING=%s", pong)


async def shutdown() -> None:
    """서버 종료 시 Valkey 연결 풀을 반환합니다."""
    await _client.aclose()
