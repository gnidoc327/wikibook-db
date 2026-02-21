import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ch05.dependencies import mongodb, mysql, opensearch, rabbitmq, s3, valkey
from ch05.dependencies.mongodb import get_database
from ch05.dependencies.mysql import get_session

# 모든 모델을 import하여 Base.metadata에 등록
import ch05.models.advertisement  # noqa: F401
import ch05.models.article  # noqa: F401
import ch05.models.board  # noqa: F401
import ch05.models.comment  # noqa: F401
import ch05.models.user  # noqa: F401

from ch05.models.article import Article
from ch05.models.comment import Comment
from ch05.routers import advertisement as ad_router
from ch05.routers import article as article_router
from ch05.routers import comment as comment_router
from ch05.routers import user as user_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def _create_master_admin() -> None:
    """최초 마스터 admin 계정을 생성합니다 (이미 존재하면 스킵)."""
    from ch05.config.config import settings
    from ch05.dependencies.mysql import _async_session
    from ch05.models.user import User, UserRole

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
    from ch05.dependencies.opensearch import _client

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
    await mongodb.startup()
    await rabbitmq.startup()
    await s3.startup()
    yield
    await rabbitmq.shutdown()
    await mongodb.shutdown()
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


class MessagePayload(BaseModel):
    routing_key: str
    body: str


@app.post(
    "/internal/messages",
    tags=["Internal"],
    summary="Consumer로부터 전달받은 RabbitMQ 메시지를 처리합니다.",
)
async def process_message(
    payload: MessagePayload,
    session: AsyncSession = Depends(get_session),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> str:
    body = json.loads(payload.body)
    msg_type = body.get("type")

    if msg_type == "write_article":
        article_id = body["article_id"]
        user_id = body["user_id"]
        article = await session.scalar(
            select(Article).where(Article.id == article_id, Article.is_deleted == False)
        )
        if article:
            await db["userNotificationHistory"].insert_one(
                {
                    "title": "글이 작성되었습니다.",
                    "content": article.title,
                    "userId": user_id,
                    "isRead": False,
                    "createdDate": datetime.now(timezone.utc),
                    "updatedDate": datetime.now(timezone.utc),
                }
            )

    elif msg_type == "write_comment":
        comment_id = body["comment_id"]
        comment = await session.scalar(
            select(Comment).where(Comment.id == comment_id, Comment.is_deleted == False)
        )
        if comment is None:
            return "ok"

        # 알림 대상: 댓글 작성자 + 게시글 작성자 + 해당 게시글의 모든 댓글 작성자
        user_ids: set[int] = set()
        if comment.author_id is not None:
            user_ids.add(comment.author_id)

        article = await session.scalar(
            select(Article).where(
                Article.id == comment.article_id, Article.is_deleted == False
            )
        )
        if article and article.author_id is not None:
            user_ids.add(article.author_id)

        other_comments = await session.scalars(
            select(Comment).where(
                Comment.article_id == comment.article_id,
                Comment.is_deleted == False,
            )
        )
        for c in other_comments.all():
            if c.author_id is not None:
                user_ids.add(c.author_id)

        now = datetime.now(timezone.utc)
        for uid in user_ids:
            await db["userNotificationHistory"].insert_one(
                {
                    "title": "댓글이 작성되었습니다.",
                    "content": comment.content,
                    "userId": uid,
                    "isRead": False,
                    "createdDate": now,
                    "updatedDate": now,
                }
            )

    logger.info("메시지 처리: routing_key=%s type=%s", payload.routing_key, msg_type)
    return "ok"
