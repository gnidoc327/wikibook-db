import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ch04.config.config import settings

logger = logging.getLogger(__name__)

# Motor(pymongo)는 내부적으로 connection pooling을 지원합니다.
# maxPoolSize로 최대 connection 수를 제한하고,
# minPoolSize로 유휴 상태에서도 유지할 최소 connection 수를 설정합니다.
_client = AsyncIOMotorClient(
    "mongodb://{user}:{passwd}@{host}:{port}".format(
        user=settings.mongodb.user,
        passwd=settings.mongodb.passwd,
        host=settings.mongodb.host,
        port=settings.mongodb.port,
    ),
    maxPoolSize=10,
    minPoolSize=10,
)

_database: AsyncIOMotorDatabase = _client[settings.mongodb.db]


def get_database() -> AsyncIOMotorDatabase:
    """
    `db: AsyncIOMotorDatabase = Depends(get_database)`로 사용
    """
    return _database


async def startup() -> None:
    """서버 시작 시 MongoDB 연결을 확인합니다."""
    result = await _database.command("ping")
    logger.info("MongoDB 연결 완료: ping=%s", result.get("ok"))


async def shutdown() -> None:
    """서버 종료 시 MongoDB 연결을 닫습니다."""
    _client.close()
