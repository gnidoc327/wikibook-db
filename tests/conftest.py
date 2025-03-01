from typing import AsyncGenerator

import httpx
import pytest
from asgi_lifespan import LifespanManager

from src.main import app


@pytest.fixture
async def test_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            limits=httpx.Limits(max_connections=1000, max_keepalive_connections=1000),
        ) as async_client,
        LifespanManager(app),
    ):
        yield async_client
