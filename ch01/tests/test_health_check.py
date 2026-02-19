import httpx


class TestHealthCheck:
    async def test_health_check(self, test_client: httpx.AsyncClient):
        response = await test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == "ok"
