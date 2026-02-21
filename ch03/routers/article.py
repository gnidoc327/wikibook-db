import logging
from datetime import datetime
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from opensearchpy import AsyncOpenSearch
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ch03.dependencies.auth import get_current_user
from ch03.dependencies.mysql import get_session
from ch03.dependencies.opensearch import get_client as get_os_client
from ch03.dependencies.valkey import get_client as get_valkey_client
from ch03.models.article import Article
from ch03.models.board import Board
from ch03.models.comment import Comment
from ch03.models.user import User

logger = logging.getLogger(__name__)

ARTICLE_INDEX = "article"
_ARTICLE_WRITE_TTL = 300  # 5분
_ARTICLE_EDIT_TTL = 300  # 5분

router = APIRouter(prefix="/boards/{board_id}/articles", tags=["Articles"])


class WriteArticleRequest(BaseModel):
    title: str
    content: str


class EditArticleRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class CommentInArticle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    author_id: int | None
    created_at: datetime | None


class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    author_id: int | None
    board_id: int | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


class ArticleDetailResponse(ArticleResponse):
    comments: list[CommentInArticle]


async def _check_write_rate_limit(user_id: int, client: aioredis.Redis) -> None:
    """Valkey 기반 게시글 작성 rate limit (5분)"""
    if await client.exists(f"rate_limit:{user_id}:article_write"):
        raise HTTPException(
            status_code=429, detail="게시글은 5분에 한 번만 작성할 수 있습니다."
        )


async def _set_write_rate_limit(user_id: int, client: aioredis.Redis) -> None:
    await client.setex(f"rate_limit:{user_id}:article_write", _ARTICLE_WRITE_TTL, "1")


async def _check_edit_rate_limit(user_id: int, client: aioredis.Redis) -> None:
    """Valkey 기반 게시글 수정/삭제 rate limit (5분)"""
    if await client.exists(f"rate_limit:{user_id}:article_edit"):
        raise HTTPException(
            status_code=429,
            detail="게시글 수정/삭제는 5분에 한 번만 할 수 있습니다.",
        )


async def _set_edit_rate_limit(user_id: int, client: aioredis.Redis) -> None:
    await client.setex(f"rate_limit:{user_id}:article_edit", _ARTICLE_EDIT_TTL, "1")


async def _index_article(client: AsyncOpenSearch, article: Article) -> None:
    """게시글을 OpenSearch에 인덱싱합니다."""
    await client.index(
        index=ARTICLE_INDEX,
        id=str(article.id),
        body={
            "title": article.title,
            "content": article.content,
            "board_id": article.board_id,
            "author_id": article.author_id,
        },
    )


async def _delete_index(client: AsyncOpenSearch, article_id: int) -> None:
    """OpenSearch에서 게시글 문서를 삭제합니다."""
    try:
        await client.delete(index=ARTICLE_INDEX, id=str(article_id))
    except Exception:
        logger.warning("OpenSearch 문서 삭제 실패: article_id=%d", article_id)


# 검색 라우트는 /{article_id} 보다 먼저 등록해야 합니다.
@router.get("/search", response_model=list[ArticleResponse])
async def search_articles(
    board_id: int,
    keyword: str = Query(..., description="검색 키워드"),
    session: AsyncSession = Depends(get_session),
    os_client: AsyncOpenSearch = Depends(get_os_client),
) -> list[Article]:
    """OpenSearch를 사용하여 게시글 content 필드에서 키워드를 검색합니다."""
    response = await os_client.search(
        index=ARTICLE_INDEX,
        body={
            "query": {
                "bool": {
                    "must": {"match": {"content": keyword}},
                    "filter": {"term": {"board_id": board_id}},
                }
            }
        },
    )
    hits = response["hits"]["hits"]
    if not hits:
        return []

    article_ids = [int(hit["_id"]) for hit in hits]
    result = await session.scalars(
        select(Article).where(
            Article.id.in_(article_ids),
            Article.board_id == board_id,
            Article.is_deleted == False,
        )
    )
    return list(result.all())


@router.post("", response_model=ArticleResponse, status_code=201)
async def write_article(
    board_id: int,
    body: WriteArticleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    os_client: AsyncOpenSearch = Depends(get_os_client),
    valkey: aioredis.Redis = Depends(get_valkey_client),
) -> Article:
    board = await session.scalar(
        select(Board).where(Board.id == board_id, Board.is_deleted == False)
    )
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")

    await _check_write_rate_limit(current_user.id, valkey)

    article = Article(
        title=body.title,
        content=body.content,
        author_id=current_user.id,
        board_id=board_id,
    )
    session.add(article)
    await session.commit()
    await session.refresh(article)

    await _set_write_rate_limit(current_user.id, valkey)
    await _index_article(os_client, article)

    return article


@router.get("", response_model=list[ArticleResponse])
async def get_articles(
    board_id: int,
    last_id: Optional[int] = Query(default=None),
    first_id: Optional[int] = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[Article]:
    stmt = select(Article).where(
        Article.board_id == board_id,
        Article.is_deleted == False,
    )

    if last_id is not None:
        stmt = stmt.where(Article.id < last_id)
    elif first_id is not None:
        stmt = stmt.where(Article.id > first_id)

    stmt = stmt.order_by(Article.id.desc()).limit(10)
    result = await session.scalars(stmt)
    return list(result.all())


@router.get("/{article_id}", response_model=ArticleDetailResponse)
async def get_article(
    board_id: int,
    article_id: int,
    session: AsyncSession = Depends(get_session),
) -> ArticleDetailResponse:
    article = await session.scalar(
        select(Article).where(
            Article.id == article_id,
            Article.board_id == board_id,
            Article.is_deleted == False,
        )
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    comments_result = await session.scalars(
        select(Comment).where(
            Comment.article_id == article_id,
            Comment.is_deleted == False,
        )
    )
    comments = [CommentInArticle.model_validate(c) for c in comments_result.all()]

    return ArticleDetailResponse(
        id=article.id,
        title=article.title,
        content=article.content,
        author_id=article.author_id,
        board_id=article.board_id,
        is_deleted=article.is_deleted,
        created_at=article.created_at,
        updated_at=article.updated_at,
        comments=comments,
    )


@router.put("/{article_id}", response_model=ArticleResponse)
async def edit_article(
    board_id: int,
    article_id: int,
    body: EditArticleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    os_client: AsyncOpenSearch = Depends(get_os_client),
    valkey: aioredis.Redis = Depends(get_valkey_client),
) -> Article:
    await _check_edit_rate_limit(current_user.id, valkey)

    article = await session.scalar(
        select(Article).where(
            Article.id == article_id,
            Article.board_id == board_id,
            Article.is_deleted == False,
        )
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="수정 권한이 없습니다.")

    if body.title is None and body.content is None:
        return article

    if body.title is not None:
        article.title = body.title
    if body.content is not None:
        article.content = body.content

    await session.commit()
    await session.refresh(article)

    await _set_edit_rate_limit(current_user.id, valkey)
    await _index_article(os_client, article)

    return article


@router.delete("/{article_id}")
async def delete_article(
    board_id: int,
    article_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    os_client: AsyncOpenSearch = Depends(get_os_client),
    valkey: aioredis.Redis = Depends(get_valkey_client),
) -> str:
    await _check_edit_rate_limit(current_user.id, valkey)

    article = await session.scalar(
        select(Article).where(
            Article.id == article_id,
            Article.board_id == board_id,
            Article.is_deleted == False,
        )
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")

    article.soft_delete()
    await session.commit()

    await _set_edit_rate_limit(current_user.id, valkey)
    await _delete_index(os_client, article_id)

    return "article is deleted"
