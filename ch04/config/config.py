from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class MySQLConfig(BaseModel):
    host: str
    user: str
    passwd: str
    port: int
    db: str


class OpenSearchConfig(BaseModel):
    host: str
    port: int


class ValkeyConfig(BaseModel):
    host: str
    port: int
    passwd: str


class MongoDBConfig(BaseModel):
    host: str
    user: str
    passwd: str
    port: int
    db: str


class Settings(BaseSettings):
    mysql: MySQLConfig
    opensearch: OpenSearchConfig
    valkey: ValkeyConfig
    mongodb: MongoDBConfig

    model_config = SettingsConfigDict(
        env_file="ch04/config/.env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


@lru_cache
def get_settings():
    return Settings()


settings: Settings = get_settings()
