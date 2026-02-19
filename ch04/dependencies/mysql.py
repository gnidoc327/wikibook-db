import logging
import sys
from typing import AsyncGenerator

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from ch04.config.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

_engine = create_async_engine(
    "mysql+asyncmy://{user}:{passwd}@{host}:{port}/{db}?charset=utf8mb4".format(
        user=settings.mysql.user,
        passwd=settings.mysql.passwd,
        host=settings.mysql.host,
        port=settings.mysql.port,
        db=settings.mysql.db,
    ),
    pool_size=10,
    max_overflow=0,
    echo=True,
    pool_pre_ping=True,
    pool_timeout=600,
)

_async_session = async_sessionmaker(
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
    async with _async_session() as session:
        yield session


def _validate_schema(sync_conn) -> list[str]:
    """
    모델 메타데이터와 실제 DB 스키마를 비교하여 불일치 항목을 반환합니다.
    """
    errors = []
    inspector = sa_inspect(sync_conn)
    existing_tables = inspector.get_table_names()

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue

        db_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
        model_columns = {col.name: col for col in table.columns}

        for col_name in model_columns:
            if col_name not in db_columns:
                errors.append(
                    f"[{table_name}] 컬럼 '{col_name}'이 모델에는 있지만 "
                    f"DB에는 없습니다."
                )

        for col_name in db_columns:
            if col_name not in model_columns:
                errors.append(
                    f"[{table_name}] 컬럼 '{col_name}'이 DB에는 있지만 "
                    f"모델에는 없습니다."
                )

        for col_name in model_columns:
            if col_name not in db_columns:
                continue
            model_col = model_columns[col_name]
            db_col = db_columns[col_name]

            if model_col.nullable != db_col["nullable"]:
                errors.append(
                    f"[{table_name}.{col_name}] nullable 불일치: "
                    f"모델={model_col.nullable}, DB={db_col['nullable']}"
                )

    return errors


async def startup() -> None:
    """서버 시작 시 MySQL 스키마 검증 및 테이블 초기화를 수행합니다."""
    async with _engine.begin() as conn:
        errors = await conn.run_sync(_validate_schema)
        if errors:
            logger.error("DB 스키마와 모델 정의가 일치하지 않습니다:")
            for error in errors:
                logger.error("  - %s", error)
            logger.error("서버를 종료합니다. DB 스키마를 확인해주세요.")
            sys.exit(1)

        await conn.run_sync(Base.metadata.create_all)
        logger.info("MySQL 테이블 초기화 완료")


async def shutdown() -> None:
    """서버 종료 시 MySQL 연결 풀을 반환합니다."""
    await _engine.dispose()
