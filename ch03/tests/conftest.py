from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import text


@pytest.fixture
async def test_client():
    with patch("ch03.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lifespan.return_value.__aexit__ = AsyncMock(return_value=None)

        from ch03.main import app

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client


@pytest.fixture(scope="session")
async def init_db():
    """
    세션 단위로 테이블을 생성합니다.
    실제 MySQL이 실행 중이어야 합니다 (docker compose up -d).
    """
    import ch03.models.advertisement  # noqa: F401
    import ch03.models.article  # noqa: F401
    import ch03.models.board  # noqa: F401
    import ch03.models.comment  # noqa: F401
    import ch03.models.user  # noqa: F401
    from ch03.dependencies.mysql import Base, _engine

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def api_client(init_db) -> httpx.AsyncClient:
    """
    실제 MySQL/Valkey와 연결된 테스트 클라이언트.
    테스트 시작 전 마스터 관리자 계정을 생성하고,
    테스트 종료 후 모든 DB 데이터와 Valkey 키를 삭제합니다.
    """
    from ch03.dependencies.mysql import _async_session
    from ch03.dependencies.valkey import _client as valkey_client
    from ch03.main import _create_master_admin, app

    await _create_master_admin()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    async with _async_session() as session:
        for table in ["comment", "article", "advertisement", "board", "user"]:
            await session.execute(text(f"DELETE FROM `{table}`"))
        await session.commit()

    await valkey_client.flushdb()


@pytest.fixture
async def admin_headers(api_client: httpx.AsyncClient) -> dict:
    """관리자 인증 헤더를 반환합니다."""
    from ch03.config.config import settings

    response = await api_client.post(
        "/users/login",
        json={
            "username": settings.admin.username,
            "password": settings.admin.password,
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def member(api_client: httpx.AsyncClient) -> dict:
    """
    일반 회원을 생성하고 {id, headers} 를 반환합니다.
    """
    sign_up = await api_client.post(
        "/users/sign-up",
        json={
            "username": "testmember",
            "email": "testmember@test.com",
            "password": "password123",
        },
    )
    assert sign_up.status_code == 200
    user_id = sign_up.json()["id"]

    login = await api_client.post(
        "/users/login",
        json={"username": "testmember", "password": "password123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"id": user_id, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
async def member_headers(member: dict) -> dict:
    return member["headers"]


@pytest.fixture
async def board_id(api_client: httpx.AsyncClient) -> int:
    """테스트용 게시판을 DB에 직접 생성합니다."""
    from ch03.dependencies.mysql import _async_session
    from ch03.models.board import Board

    async with _async_session() as session:
        board = Board(title="테스트 게시판", description="테스트 게시판 설명")
        session.add(board)
        await session.commit()
        await session.refresh(board)
        return board.id


@pytest.fixture
async def article_id(board_id: int, member: dict) -> int:
    """
    테스트용 게시글을 DB에 직접 생성합니다.
    Valkey 기반 rate limit이므로 타임스탬프 백데이트 불필요.
    """
    from ch03.dependencies.mysql import _async_session
    from ch03.models.article import Article

    async with _async_session() as session:
        article = Article(
            title="테스트 게시글",
            content="테스트 내용",
            author_id=member["id"],
            board_id=board_id,
        )
        session.add(article)
        await session.commit()
        await session.refresh(article)
        return article.id
