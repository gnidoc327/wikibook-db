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


class S3Config(BaseModel):
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket_name: str
    region: str = "us-east-1"


class Settings(BaseSettings):
    mysql: MySQLConfig
    opensearch: OpenSearchConfig

    s3: S3Config

    model_config = SettingsConfigDict(
        env_file="ch02/config/.env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


@lru_cache
def get_settings():
    return Settings()


settings: Settings = get_settings()
