from unittest.mock import AsyncMock, patch

import httpx
import pytest


@pytest.fixture
async def test_client():
    """
    DB 연결 없이 API 테스트를 위한 클라이언트.
    lifespan을 mock하여 실제 DB 연결을 하지 않습니다.
    """
    with patch("ch01.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_lifespan.return_value.__aexit__ = AsyncMock(return_value=None)

        from ch01.main import app

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
