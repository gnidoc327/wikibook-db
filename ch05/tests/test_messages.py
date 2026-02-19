import httpx


class TestProcessMessage:
    async def test_process_message(self, test_client: httpx.AsyncClient):
        response = await test_client.post(
            "/internal/messages",
            json={"routing_key": "wikibook.test", "body": "hello"},
        )
        assert response.status_code == 200
        assert response.json() == "ok"

    async def test_process_message_missing_field(self, test_client: httpx.AsyncClient):
        response = await test_client.post(
            "/internal/messages",
            json={"routing_key": "wikibook.test"},
        )
        assert response.status_code == 422
