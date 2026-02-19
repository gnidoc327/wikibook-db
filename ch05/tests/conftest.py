from unittest.mock import AsyncMock, patch

import httpx
import pytest


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
