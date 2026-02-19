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
