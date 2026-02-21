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


class RabbitMQConfig(BaseModel):
    host: str
    user: str
    passwd: str
    port: int


class ConsumerConfig(BaseModel):
    fastapi_url: str = "http://127.0.0.1:8000"
    exchange_name: str
    queue_name: str
    routing_key: str = "#"


class S3Config(BaseModel):
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket_name: str
    region: str = "us-east-1"


class JwtConfig(BaseModel):
    secret_key: str
    algorithm: str = "HS256"
    expire_minutes: int = 60


class AdminConfig(BaseModel):
    username: str = "admin"
    email: str = "admin@localhost"
    password: str


class Settings(BaseSettings):
    mysql: MySQLConfig
    opensearch: OpenSearchConfig
    valkey: ValkeyConfig
    mongodb: MongoDBConfig
    rabbitmq: RabbitMQConfig
    consumer: ConsumerConfig
    s3: S3Config
    jwt: JwtConfig
    admin: AdminConfig

    model_config = SettingsConfigDict(
        env_file="ch05/config/.env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )


@lru_cache
def get_settings():
    return Settings()


settings: Settings = get_settings()
