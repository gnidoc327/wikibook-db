import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect as sa_inspect

from ch04.dependencies.mysql import Base, _engine
from ch04.dependencies.opensearch import _client as opensearch_client
from ch04.dependencies.valkey import _client as valkey_client
from ch04.dependencies.mongodb import _client as mongodb_client, _database

import ch04.models.user  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # MySQL 스키마 검증 및 테이블 생성
    async with _engine.begin() as conn:
        errors = await conn.run_sync(_validate_schema)
        if errors:
            logger.error("DB 스키마와 모델 정의가 일치하지 않습니다:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.error("서버를 종료합니다. DB 스키마를 확인해주세요.")
            sys.exit(1)

        await conn.run_sync(Base.metadata.create_all)
        logger.info("MySQL 테이블 초기화 완료")

    # OpenSearch 연결 확인
    info = await opensearch_client.info()
    logger.info(
        "OpenSearch 연결 완료: %s (v%s)",
        info["cluster_name"],
        info["version"]["number"],
    )

    # Valkey 연결 확인
    pong = await valkey_client.ping()
    logger.info("Valkey 연결 완료: PING=%s", pong)

    # MongoDB 연결 확인
    result = await _database.command("ping")
    logger.info("MongoDB 연결 완료: ping=%s", result.get("ok"))

    yield

    mongodb_client.close()
    await valkey_client.aclose()
    await opensearch_client.close()
    await _engine.dispose()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["Health Check"],
    summary="Health Check용 API",
)
async def health_check() -> str:
    return "ok"
