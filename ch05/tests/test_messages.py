import json

import httpx


class TestProcessMessage:
    async def test_missing_body_field(self, test_client: httpx.AsyncClient):
        """body 필드가 없으면 422를 반환합니다."""
        response = await test_client.post(
            "/internal/messages",
            json={"routing_key": "wikibook.test"},
        )
        assert response.status_code == 422

    async def test_unknown_type(self, api_client: httpx.AsyncClient):
        """알 수 없는 type의 메시지는 무시하고 ok를 반환합니다."""
        response = await api_client.post(
            "/internal/messages",
            json={
                "routing_key": "test",
                "body": json.dumps({"type": "unknown_type"}),
            },
        )
        assert response.status_code == 200
        assert response.json() == "ok"

    async def test_write_article_saves_notification(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member_headers: dict,
        member: dict,
    ):
        """write_article 메시지 처리 시 MongoDB userNotificationHistory에 알림이 저장됩니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        # 게시글 작성 (savepoint 세션에서 생성 → process_message에서 조회 가능)
        write_resp = await api_client.post(
            f"/boards/{board_id}/articles",
            json={"title": "알림 테스트 게시글", "content": "내용"},
            headers=member_headers,
        )
        assert write_resp.status_code == 201
        article_id = write_resp.json()["id"]

        # Consumer가 호출하는 것처럼 /internal/messages 직접 호출
        response = await api_client.post(
            "/internal/messages",
            json={
                "routing_key": "article.created",
                "body": json.dumps(
                    {
                        "type": "write_article",
                        "article_id": article_id,
                        "user_id": member["id"],
                    }
                ),
            },
        )
        assert response.status_code == 200
        assert response.json() == "ok"

        # MongoDB에 알림 1건 저장 확인
        count = await mongo_db["userNotificationHistory"].count_documents(
            {"userId": member["id"]}
        )
        assert count == 1

    async def test_write_article_nonexistent(self, api_client: httpx.AsyncClient):
        """존재하지 않는 게시글에 대한 알림 메시지는 MongoDB에 저장하지 않고 ok를 반환합니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        response = await api_client.post(
            "/internal/messages",
            json={
                "routing_key": "article.created",
                "body": json.dumps(
                    {"type": "write_article", "article_id": 99999, "user_id": 1}
                ),
            },
        )
        assert response.status_code == 200
        assert response.json() == "ok"

        count = await mongo_db["userNotificationHistory"].count_documents({})
        assert count == 0

    async def test_write_comment_saves_notification(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
        member: dict,
    ):
        """write_comment 메시지 처리 시 관련 사용자 모두에게 알림이 저장됩니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        # 댓글 작성 (savepoint 세션에서 생성 → process_message에서 조회 가능)
        write_resp = await api_client.post(
            f"/boards/{board_id}/articles/{article_id}/comments",
            json={"content": "알림 테스트 댓글"},
            headers=member_headers,
        )
        assert write_resp.status_code == 201
        comment_id = write_resp.json()["id"]

        response = await api_client.post(
            "/internal/messages",
            json={
                "routing_key": "comment.created",
                "body": json.dumps({"type": "write_comment", "comment_id": comment_id}),
            },
        )
        assert response.status_code == 200
        assert response.json() == "ok"

        # 댓글 작성자 = 게시글 작성자 = member → unique 1명 → 알림 1건
        count = await mongo_db["userNotificationHistory"].count_documents(
            {"userId": member["id"]}
        )
        assert count == 1

    async def test_write_comment_nonexistent(self, api_client: httpx.AsyncClient):
        """존재하지 않는 댓글에 대한 메시지는 MongoDB에 저장하지 않고 ok를 반환합니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        response = await api_client.post(
            "/internal/messages",
            json={
                "routing_key": "comment.created",
                "body": json.dumps({"type": "write_comment", "comment_id": 99999}),
            },
        )
        assert response.status_code == 200
        assert response.json() == "ok"

        count = await mongo_db["userNotificationHistory"].count_documents({})
        assert count == 0
