import asyncio
import fcntl
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def test_client():
    with patch("ch05.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lifespan.return_value.__aexit__ = AsyncMock(return_value=None)

        from ch05.main import app

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
    import ch05.models.advertisement  # noqa: F401
    import ch05.models.article  # noqa: F401
    import ch05.models.board  # noqa: F401
    import ch05.models.comment  # noqa: F401
    import ch05.models.user  # noqa: F401

    import ch05.dependencies.rabbitmq as rabbitmq_mod
    from ch05.dependencies.mongodb import shutdown as mongodb_shutdown
    from ch05.dependencies.mysql import Base, _engine, shutdown as mysql_shutdown
    from ch05.dependencies.opensearch import shutdown as opensearch_shutdown
    from ch05.dependencies.valkey import shutdown as valkey_shutdown
    from ch05.main import _create_master_admin

    base = tmp_path_factory.getbasetemp().parent  # 모든 xdist 워커가 공유하는 경로
    lock_path = str(base / "ch05_init.lock")
    done_path = base / "ch05_init.done"

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

    # 워커별 Valkey DB 분리: flushdb() race condition 방지
    # gw0→DB1, gw1→DB2, ..., master→DB1 (각 워커가 독립된 DB를 사용)
    import redis.asyncio as aioredis

    import ch05.dependencies.mongodb as mongodb_mod
    import ch05.dependencies.valkey as valkey_mod
    from ch05.config.config import settings

    db_num = int(worker_id.lstrip("gw")) + 1 if worker_id.startswith("gw") else 1
    valkey_mod._client = aioredis.Redis(
        connection_pool=aioredis.ConnectionPool(
            host=settings.valkey.host,
            port=settings.valkey.port,
            password=settings.valkey.passwd,
            db=db_num,
            max_connections=10,
            decode_responses=True,
        )
    )

    # 워커별 MongoDB database 분리: delete_many({}) race condition 방지
    db_suffix = worker_id if worker_id.startswith("gw") else "master"
    worker_mongo_db = f"{settings.mongodb.db}_{db_suffix}"
    mongodb_mod._database = mongodb_mod._client[worker_mongo_db]

    # 워커별 RabbitMQ 연결 (publish 호출에 필요)
    await rabbitmq_mod.startup()

    yield

    await rabbitmq_mod.shutdown()
    await mongodb_mod._client.drop_database(worker_mongo_db)
    await opensearch_shutdown()
    await valkey_shutdown()
    await mongodb_shutdown()
    await mysql_shutdown()


@pytest.fixture(scope="session")
async def admin_headers(init_db) -> dict:
    """관리자 JWT 토큰을 직접 생성합니다."""
    from ch05.config.config import settings
    from ch05.dependencies.auth import create_access_token

    token = create_access_token(settings.admin.username)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
async def member(init_db, worker_id) -> dict:
    """
    워커별 고유한 일반 회원을 DB에 직접 생성합니다.
    JWT 토큰도 직접 생성하여 반환합니다.
    """
    from ch05.dependencies.auth import create_access_token
    from ch05.dependencies.mysql import _async_session
    from ch05.models.user import User, UserRole

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
    return {
        "id": user_id,
        "username": username,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture(scope="session")
async def member_headers(member: dict) -> dict:
    return member["headers"]


@pytest.fixture(scope="session")
async def board_id(init_db) -> int:
    """테스트용 게시판을 DB에 직접 생성합니다 (세션당 1회)."""
    from ch05.dependencies.mysql import _async_session
    from ch05.models.board import Board

    async with _async_session() as session:
        board = Board(title="테스트 게시판", description="테스트 게시판 설명")
        session.add(board)
        await session.commit()
        await session.refresh(board)
        return board.id


@pytest.fixture(scope="session")
async def article_id(board_id: int, member: dict) -> int:
    """
    테스트용 게시글을 DB에 직접 생성합니다.
    Valkey 기반 rate limit이므로 타임스탬프 백데이트 불필요.
    """
    from ch05.dependencies.mysql import _async_session
    from ch05.models.article import Article

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


# ── 테스트 단위 픽스처 (savepoint 트랜잭션 격리 + 외부 상태 초기화) ─────────────


@pytest.fixture(autouse=True)
async def _external_cleanup():
    """각 테스트 종료 후 Valkey와 MongoDB를 초기화합니다."""
    yield
    from ch05.dependencies.mongodb import _database as mongo_db
    from ch05.dependencies.valkey import _client as valkey_client

    await valkey_client.flushdb()
    await mongo_db["adViewHistory"].delete_many({})
    await mongo_db["adClickHistory"].delete_many({})
    await mongo_db["userNotificationHistory"].delete_many({})


@pytest.fixture
async def _test_conn(init_db):
    """
    테스트별 DB 격리를 위한 savepoint 트랜잭션 픽스처.
    get_session dependency를 override해 route handler가 같은 세션을 사용하게 합니다.
    테스트 종료 후 outer transaction을 rollback해 모든 변경사항을 되돌립니다.
    """
    from ch05.dependencies.mysql import _engine, get_session
    from ch05.main import app

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
    from ch05.main import app

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
