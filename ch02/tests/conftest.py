import asyncio
import fcntl
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_client():
    """
    DB 연결 없이 API 테스트를 위한 클라이언트.
    lifespan을 mock하여 실제 DB 연결을 하지 않습니다.
    """
    with patch("ch02.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lifespan.return_value.__aexit__ = AsyncMock(return_value=None)

        from ch02.main import app

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client


# ── 세션 단위 픽스처 (챕터당 1회 생성) ─────────────────────────────────────────


@pytest.fixture(scope="session")
async def init_db(tmp_path_factory, worker_id):
    """
    MySQL 스키마를 DROP+CREATE 후 마스터 어드민을 생성합니다.
    pytest-xdist 환경에서 여러 워커가 동시에 실행될 때
    파일 락을 사용해 초기화를 한 번만 수행합니다.
    """
    import ch02.models.article  # noqa: F401
    import ch02.models.board  # noqa: F401
    import ch02.models.comment  # noqa: F401
    import ch02.models.jwt_blacklist  # noqa: F401
    import ch02.models.user  # noqa: F401
    from ch02.dependencies.mysql import Base, _engine, shutdown as mysql_shutdown
    from ch02.dependencies.opensearch import shutdown as opensearch_shutdown
    from ch02.main import _create_master_admin

    base = tmp_path_factory.getbasetemp().parent  # 모든 xdist 워커가 공유하는 경로
    lock_path = str(base / "ch02_init.lock")
    done_path = base / "ch02_init.done"

    def _try_lock():
        """
        배타적 파일 락을 획득합니다.
        done_path가 없으면 락을 유지한 채 lock file 객체를 반환합니다 (이 워커가 초기화 담당).
        done_path가 있으면 락을 해제하고 None을 반환합니다 (다른 워커가 이미 초기화 완료).
        """
        lf = open(lock_path, "w")
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        if done_path.exists():
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            lf.close()
            return None
        return lf  # 락 유지한 채 반환

    # blocking flock을 별도 스레드에서 실행하여 이벤트 루프 블로킹 방지
    lock_file = await asyncio.to_thread(_try_lock)
    try:
        if lock_file is not None:
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
            await _create_master_admin()
            done_path.write_text("done")
    finally:
        if lock_file is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    yield
    await opensearch_shutdown()
    await mysql_shutdown()


@pytest.fixture(scope="session")
async def admin_headers(init_db) -> dict:
    """관리자 JWT 토큰을 직접 생성합니다."""
    from ch02.config.config import settings
    from ch02.dependencies.auth import create_access_token

    token = create_access_token(settings.admin.username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
async def member(init_db, worker_id) -> dict:
    """
    워커별 고유한 일반 회원을 DB에 직접 생성합니다.
    JWT 토큰도 직접 생성하여 반환합니다.
    """
    from ch02.dependencies.auth import create_access_token
    from ch02.dependencies.mysql import _async_session
    from ch02.models.user import User, UserRole

    username = f"testmember_{worker_id}"
    async with _async_session() as session:
        user = User(
            username=username,
            email=f"{username}@test.com",
            role=UserRole.member,
        )
        user.set_password("password123")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(username)
    return {"id": user_id, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(scope="session")
async def member_headers(member: dict) -> dict:
    return member["headers"]


@pytest.fixture(scope="session")
async def board_id(init_db) -> int:
    """테스트용 게시판을 DB에 직접 생성합니다 (세션당 1회)."""
    from ch02.dependencies.mysql import _async_session
    from ch02.models.board import Board

    async with _async_session() as session:
        board = Board(title="테스트 게시판", description="테스트 게시판 설명")
        session.add(board)
        await session.commit()
        await session.refresh(board)
        return board.id


@pytest.fixture(scope="session")
async def article_id(board_id: int, member: dict) -> int:
    """테스트용 게시글을 DB에 직접 생성합니다 (rate limit 우회를 위해 타임스탬프 백데이트)."""
    from sqlalchemy import text

    from ch02.dependencies.mysql import _async_session
    from ch02.models.article import Article

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
        article_id = article.id
        await session.execute(
            text(
                "UPDATE article SET created_at = NOW() - INTERVAL 6 MINUTE,"
                " updated_at = NOW() - INTERVAL 6 MINUTE WHERE id = :id"
            ),
            {"id": article_id},
        )
        await session.commit()
        return article_id


# ── 테스트 단위 픽스처 (savepoint 트랜잭션 격리) ────────────────────────────────


@pytest.fixture
async def _test_conn(init_db):
    """
    테스트별 DB 격리를 위한 savepoint 트랜잭션 픽스처.
    get_session dependency를 override해 route handler가 같은 세션을 사용하게 합니다.
    테스트 종료 후 outer transaction을 rollback해 모든 변경사항을 되돌립니다.
    """
    from ch02.dependencies.mysql import _engine, get_session
    from ch02.main import app

    conn = await _engine.connect()
    await conn.begin()
    session = AsyncSession(
        bind=conn,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    try:
        yield conn, session
    finally:
        app.dependency_overrides.pop(get_session, None)
        await session.close()
        await conn.rollback()
        await conn.close()


@pytest.fixture
async def api_client(_test_conn) -> httpx.AsyncClient:
    """savepoint 세션을 사용하는 테스트용 HTTP 클라이언트."""
    from ch02.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
async def db_session(_test_conn) -> AsyncSession:
    """
    rate limit 우회 등 DB 직접 조작이 필요한 테스트를 위한 세션.
    api_client와 동일한 savepoint 트랜잭션을 공유합니다.
    """
    _, session = _test_conn
    return session
