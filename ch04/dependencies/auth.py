from datetime import datetime, timedelta, timezone

import jwt
import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ch04.config.config import settings
from ch04.dependencies.mysql import get_session
from ch04.dependencies.valkey import get_client
from ch04.models.user import User


def create_access_token(username: str) -> str:
    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=settings.jwt.expire_minutes),
    }
    return jwt.encode(
        payload, settings.jwt.secret_key, algorithm=settings.jwt.algorithm
    )


async def get_current_user(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
    client: aioredis.Redis = Depends(get_client),
) -> User:
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=422, detail="Invalid authentication scheme")
    except ValueError as e:
        raise HTTPException(
            status_code=422, detail="Invalid authorization header format"
        ) from e

    if await client.exists(f"jwt_blacklist:{token}"):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm],
        )
        username: str = payload.get("sub")
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


async def get_optional_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
    client: aioredis.Redis = Depends(get_client),
) -> User | None:
    """인증이 선택적인 엔드포인트에서 사용합니다. 미인증이면 None을 반환합니다."""
    if authorization is None:
        return None
    try:
        return await get_current_user(authorization, session, client)
    except HTTPException:
        return None
