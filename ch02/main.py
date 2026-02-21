import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from ch02.config.config import settings
from ch02.dependencies import mysql, opensearch, s3
from ch02.dependencies.mysql import _async_session
from ch02.dependencies.opensearch import _client as _os_client
from ch02.models.user import User, UserRole
from ch02.routers import article, comment, user

# 모든 모델을 import하여 Base.metadata에 등록
import ch02.models.article  # noqa: F401
import ch02.models.board  # noqa: F401
import ch02.models.comment  # noqa: F401
import ch02.models.jwt_blacklist  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

ARTICLE_INDEX = "article"


async def _create_master_admin() -> None:
    """마스터 admin 계정이 없을 경우 자동 생성합니다."""
    async with _async_session() as session:
        existing = await session.scalar(
            select(User).where(User.username == settings.admin.username)
        )
        if existing is None:
            admin = User(
                username=settings.admin.username,
                email=settings.admin.email,
                role=UserRole.admin,
            )
            admin.set_password(settings.admin.password)
            session.add(admin)
            await session.commit()
            logger.info("마스터 관리자 계정 생성 완료: %s", settings.admin.username)
        else:
            logger.info(
                "마스터 관리자 계정이 이미 존재합니다: %s", settings.admin.username
            )


async def _init_opensearch_index() -> None:
    """OpenSearch article 인덱스가 없으면 생성합니다."""
    exists = await _os_client.indices.exists(index=ARTICLE_INDEX)
    if not exists:
        await _os_client.indices.create(
            index=ARTICLE_INDEX,
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
        logger.info("OpenSearch '%s' 인덱스 생성 완료", ARTICLE_INDEX)
    else:
        logger.info("OpenSearch '%s' 인덱스가 이미 존재합니다", ARTICLE_INDEX)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await mysql.startup()
    await _create_master_admin()
    await opensearch.startup()
    await _init_opensearch_index()
    await s3.startup()
    yield
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

app.include_router(user.router)
app.include_router(article.router)
app.include_router(comment.router)


@app.get(
    "/health",
    tags=["Health Check"],
    summary="Health Check용 API",
)
async def health_check() -> str:
    return "ok"
