import logging
from datetime import datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ch03.dependencies.auth import get_current_user
from ch03.dependencies.mysql import get_session
from ch03.dependencies.valkey import get_client as get_valkey_client
from ch03.models.article import Article
from ch03.models.comment import Comment
from ch03.models.user import User

logger = logging.getLogger(__name__)

_COMMENT_WRITE_TTL = 60  # 1분
_COMMENT_EDIT_TTL = 60  # 1분

router = APIRouter(
    prefix="/boards/{board_id}/articles/{article_id}/comments",
    tags=["Comments"],
)


class WriteCommentRequest(BaseModel):
    content: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    author_id: int | None
    article_id: int | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


async def _check_comment_rate_limit(user_id: int, client: aioredis.Redis) -> None:
    """Valkey 기반 댓글 작성 rate limit (1분)"""
    if await client.exists(f"rate_limit:{user_id}:comment_write"):
        raise HTTPException(
            status_code=429, detail="댓글은 1분에 한 번만 작성할 수 있습니다."
        )


async def _set_comment_rate_limit(user_id: int, client: aioredis.Redis) -> None:
    await client.setex(f"rate_limit:{user_id}:comment_write", _COMMENT_WRITE_TTL, "1")


async def _check_comment_edit_rate_limit(user_id: int, client: aioredis.Redis) -> None:
    """Valkey 기반 댓글 수정/삭제 rate limit (1분)"""
    if await client.exists(f"rate_limit:{user_id}:comment_edit"):
        raise HTTPException(
            status_code=429, detail="댓글 수정/삭제는 1분에 한 번만 할 수 있습니다."
        )


async def _set_comment_edit_rate_limit(user_id: int, client: aioredis.Redis) -> None:
    await client.setex(f"rate_limit:{user_id}:comment_edit", _COMMENT_EDIT_TTL, "1")


async def _get_active_article(
    board_id: int, article_id: int, session: AsyncSession
) -> Article:
    article = await session.scalar(
        select(Article).where(
            Article.id == article_id,
            Article.board_id == board_id,
            Article.is_deleted == False,
        )
    )
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("", response_model=CommentResponse, status_code=201)
async def write_comment(
    board_id: int,
    article_id: int,
    body: WriteCommentRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    valkey: aioredis.Redis = Depends(get_valkey_client),
) -> Comment:
    await _check_comment_rate_limit(current_user.id, valkey)
    await _get_active_article(board_id, article_id, session)

    comment = Comment(
        content=body.content,
        author_id=current_user.id,
        article_id=article_id,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    await _set_comment_rate_limit(current_user.id, valkey)

    return comment


@router.put("/{comment_id}", response_model=CommentResponse)
async def edit_comment(
    board_id: int,
    article_id: int,
    comment_id: int,
    body: WriteCommentRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    valkey: aioredis.Redis = Depends(get_valkey_client),
) -> Comment:
    await _check_comment_edit_rate_limit(current_user.id, valkey)
    await _get_active_article(board_id, article_id, session)

    comment = await session.scalar(
        select(Comment).where(
            Comment.id == comment_id,
            Comment.article_id == article_id,
            Comment.is_deleted == False,
        )
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="수정 권한이 없습니다.")

    comment.content = body.content
    await session.commit()
    await session.refresh(comment)

    await _set_comment_edit_rate_limit(current_user.id, valkey)

    return comment


@router.delete("/{comment_id}")
async def delete_comment(
    board_id: int,
    article_id: int,
    comment_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    valkey: aioredis.Redis = Depends(get_valkey_client),
) -> str:
    await _check_comment_edit_rate_limit(current_user.id, valkey)
    await _get_active_article(board_id, article_id, session)

    comment = await session.scalar(
        select(Comment).where(
            Comment.id == comment_id,
            Comment.article_id == article_id,
            Comment.is_deleted == False,
        )
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")

    comment.soft_delete()
    await session.commit()

    await _set_comment_edit_rate_limit(current_user.id, valkey)

    return "comment is deleted"
