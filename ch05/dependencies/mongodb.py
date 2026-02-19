import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ch05.config.config import settings

logger = logging.getLogger(__name__)

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
