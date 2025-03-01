from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class MySQLConfig(BaseModel):
    host: str
    user: str
    passwd: str
    port: int
    db: str


class RedisConfig(BaseModel):
    host: str
    user: str
    passwd: str
    port: int


class MongoDBConfig(BaseModel):
    host: str
    user: str
    passwd: str
    port: int
    db: str


class ESConfig(BaseModel):
    host: str
    user: str
    passwd: str
    port: int


class RabbitMQConfig(BaseModel):
    host: str
    user: str
    passwd: str
    port: int


class Settings(BaseSettings):
    """
    기본 Configuration
    """

    mysql: MySQLConfig
    redis: RedisConfig
    mongodb: MongoDBConfig
    es: ESConfig
    rabbitmq: RabbitMQConfig

    model_config = SettingsConfigDict(
        env_file="src/config/.env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        # extra="ignore"
    )


@lru_cache
def get_settings():
    return Settings()


settings: Settings = get_settings()
