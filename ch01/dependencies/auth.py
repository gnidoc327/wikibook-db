import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ch01.config.config import settings
from ch01.dependencies.mysql import get_session
from ch01.models.jwt_blacklist import JwtBlacklist
from ch01.models.user import User

logger = logging.getLogger(__name__)


def create_access_token(username: str) -> str:
    """JWT 액세스 토큰을 생성합니다."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt.expire_minutes),
    }
    return jwt.encode(
        payload, settings.jwt.secret_key, algorithm=settings.jwt.algorithm
    )


async def get_current_user(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Authorization 헤더에서 JWT 토큰을 추출하여 현재 사용자를 반환합니다."""
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    except ValueError as e:
        raise HTTPException(
            status_code=401, detail="Invalid authorization header format"
        ) from e

    blacklisted = await session.scalar(
        select(JwtBlacklist).where(JwtBlacklist.token == token)
    )
    if blacklisted:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm],
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e

    user = await session.scalar(
        select(User).where(User.username == username, User.is_deleted == False)
    )
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user
