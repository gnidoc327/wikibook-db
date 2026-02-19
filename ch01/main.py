import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect as sa_inspect

from ch01.dependencies.mysql import Base, _engine

# 모든 모델을 import하여 Base.metadata에 등록
import ch01.models.user  # noqa: F401

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

        # 모델에 있지만 DB에 없는 컬럼
        for col_name in model_columns:
            if col_name not in db_columns:
                errors.append(
                    f"[{table_name}] 컬럼 '{col_name}'이 모델에는 있지만 "
                    f"DB에는 없습니다."
                )

        # DB에 있지만 모델에 없는 컬럼
        for col_name in db_columns:
            if col_name not in model_columns:
                errors.append(
                    f"[{table_name}] 컬럼 '{col_name}'이 DB에는 있지만 "
                    f"모델에는 없습니다."
                )

        # 공통 컬럼의 nullable 비교
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
    async with _engine.begin() as conn:
        # 1. 기존 테이블과 모델 스키마 비교
        errors = await conn.run_sync(_validate_schema)
        if errors:
            logger.error("DB 스키마와 모델 정의가 일치하지 않습니다:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.error("서버를 종료합니다. DB 스키마를 확인해주세요.")
            sys.exit(1)

        # 2. 존재하지 않는 테이블만 생성
        await conn.run_sync(Base.metadata.create_all)
        logger.info("DB 테이블 초기화 완료")

    yield

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
