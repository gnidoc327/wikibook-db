import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ch01.config.config import settings
from ch01.dependencies.auth import create_access_token, get_current_user
from ch01.dependencies.mysql import get_session
from ch01.models.jwt_blacklist import JwtBlacklist
from ch01.models.user import User, UserRole

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

router = APIRouter(prefix="/users", tags=["Users"])


class SignUpRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: UserRole
    last_login: datetime | None
    created_at: datetime | None


class UpdateRoleRequest(BaseModel):
    role: UserRole


@router.get("", response_model=list[UserResponse])
async def get_users(
    _current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[User]:
    result = await session.scalars(select(User).where(User.is_deleted == False))
    return list(result.all())


@router.post("/sign-up", response_model=UserResponse)
async def sign_up(
    body: SignUpRequest,
    session: AsyncSession = Depends(get_session),
) -> User:
    user = User(username=body.username, email=body.email, role=UserRole.member)
    user.set_password(body.password)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="이미 사용 중인 사용자명 또는 이메일입니다."
        ) from e
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    if current_user.id != user_id and current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")
    user = await session.scalar(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.soft_delete()
    await session.commit()


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    user = await session.scalar(
        select(User).where(User.username == body.username, User.is_deleted == False)
    )
    if user is None or not user.verify_password(body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user.last_login = datetime.now(KST).replace(tzinfo=None)
    await session.commit()

    token = create_access_token(user.username)
    return LoginResponse(access_token=token)


@router.post("/logout")
async def logout(
    _current_user: User = Depends(get_current_user),
) -> str:
    """로그아웃 (클라이언트에서 토큰 폐기)"""
    return "ok"


@router.post("/logout/all")
async def logout_all(
    authorization: str = Header(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> str:
    """전체 로그아웃 (토큰을 블랙리스트에 등록)"""
    token = authorization.split(" ", 1)[1]

    payload = jwt.decode(
        token,
        settings.jwt.secret_key,
        algorithms=[settings.jwt.algorithm],
    )
    exp = datetime.fromtimestamp(payload["exp"], tz=KST).replace(tzinfo=None)

    blacklist = JwtBlacklist(
        token=token,
        expiration_time=exp,
        username=current_user.username,
    )
    session.add(blacklist)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
    return "ok"


@router.post("/token/validation")
async def validate_token(
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session),
) -> str:
    """토큰 유효성 검증"""
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
        raise HTTPException(status_code=403, detail="Token has been revoked")

    try:
        jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm],
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=403, detail="Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=403, detail="Invalid token") from e

    return "ok"


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    body: UpdateRoleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """유저 권한 변경 (admin 전용)"""
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=403, detail="관리자만 권한을 변경할 수 있습니다."
        )
    user = await session.scalar(
        select(User).where(User.id == user_id, User.is_deleted == False)
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role
    await session.commit()
    await session.refresh(user)
    return user
