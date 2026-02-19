import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ch01.dependencies.auth import get_current_user
from ch01.dependencies.mysql import get_session
from ch01.models.article import Article
from ch01.models.board import Board
from ch01.models.comment import Comment
from ch01.models.user import User

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

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


async def _check_write_rate_limit(author_id: int, session: AsyncSession) -> None:
    """게시글 작성 rate limit 검사 (5분)"""
    last = await session.scalar(
        select(Article)
        .where(Article.author_id == author_id)
        .order_by(Article.created_at.desc())
        .limit(1)
    )
    if last and last.created_at:
        diff = datetime.now(KST).replace(tzinfo=None) - last.created_at
        if diff < timedelta(minutes=5):
            raise HTTPException(
                status_code=429, detail="게시글은 5분에 한 번만 작성할 수 있습니다."
            )


async def _check_edit_rate_limit(author_id: int, session: AsyncSession) -> None:
    """게시글 수정/삭제 rate limit 검사 (5분)"""
    last = await session.scalar(
        select(Article)
        .where(Article.author_id == author_id)
        .order_by(Article.updated_at.desc())
        .limit(1)
    )
    if last and last.updated_at:
        diff = datetime.now(KST).replace(tzinfo=None) - last.updated_at
        if diff < timedelta(minutes=5):
            raise HTTPException(
                status_code=429,
                detail="게시글 수정/삭제는 5분에 한 번만 할 수 있습니다.",
            )


@router.post("", response_model=ArticleResponse, status_code=201)
async def write_article(
    board_id: int,
    body: WriteArticleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Article:
    board = await session.scalar(
        select(Board).where(Board.id == board_id, Board.is_deleted == False)
    )
    if board is None:
        raise HTTPException(status_code=404, detail="Board not found")

    await _check_write_rate_limit(current_user.id, session)

    article = Article(
        title=body.title,
        content=body.content,
        author_id=current_user.id,
        board_id=board_id,
    )
    session.add(article)
    await session.commit()
    await session.refresh(article)
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
) -> Article:
    await _check_edit_rate_limit(current_user.id, session)

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
    return article


@router.delete("/{article_id}")
async def delete_article(
    board_id: int,
    article_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> str:
    await _check_edit_rate_limit(current_user.id, session)

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
    return "article is deleted"
