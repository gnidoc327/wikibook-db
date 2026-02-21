import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from ch03.dependencies import mysql, opensearch, s3, valkey

# 모든 모델을 import하여 Base.metadata에 등록
import ch03.models.advertisement  # noqa: F401
import ch03.models.article  # noqa: F401
import ch03.models.board  # noqa: F401
import ch03.models.comment  # noqa: F401
import ch03.models.user  # noqa: F401

from ch03.routers import advertisement as ad_router
from ch03.routers import article as article_router
from ch03.routers import comment as comment_router
from ch03.routers import user as user_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def _create_master_admin() -> None:
    """최초 마스터 admin 계정을 생성합니다 (이미 존재하면 스킵)."""
    from ch03.config.config import settings
    from ch03.dependencies.mysql import _async_session
    from ch03.models.user import User, UserRole

    async with _async_session() as session:
        existing = await session.scalar(
            select(User).where(User.username == settings.admin.username)
        )
        if existing is not None:
            return

        admin = User(
            username=settings.admin.username,
            email=settings.admin.email,
            role=UserRole.admin,
        )
        admin.set_password(settings.admin.password)
        session.add(admin)
        await session.commit()
        logger.info("마스터 admin 계정 생성 완료: %s", settings.admin.username)


async def _init_opensearch_index() -> None:
    """OpenSearch article 인덱스를 생성합니다 (이미 존재하면 스킵)."""
    from ch03.dependencies.opensearch import _client

    index_name = "article"
    if await _client.indices.exists(index=index_name):
        return

    await _client.indices.create(
        index=index_name,
        body={
            "mappings": {
                "properties": {
                    "title": {"type": "text"},
                    "content": {"type": "text"},
                    "board_id": {"type": "integer"},
                    "author_id": {"type": "integer"},
                }
            }
        },
    )
    logger.info("OpenSearch 인덱스 생성 완료: %s", index_name)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await mysql.startup()
    await _create_master_admin()
    await opensearch.startup()
    await _init_opensearch_index()
    await valkey.startup()
    await s3.startup()
    yield
    await valkey.shutdown()
    await opensearch.shutdown()
    await mysql.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router.router)
app.include_router(article_router.router)
app.include_router(comment_router.router)
app.include_router(ad_router.router)


@app.get(
    "/health",
    tags=["Health Check"],
    summary="Health Check용 API",
)
async def health_check() -> str:
    return "ok"
