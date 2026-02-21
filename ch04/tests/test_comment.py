import httpx
from sqlalchemy.ext.asyncio import AsyncSession


class TestWriteComment:
    async def test_success(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        response = await api_client.post(
            f"/boards/{board_id}/articles/{article_id}/comments",
            json={"content": "테스트 댓글"},
            headers=member_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "테스트 댓글"
        assert data["article_id"] == article_id
        assert data["is_deleted"] is False

    async def test_article_not_found(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member_headers: dict,
    ):
        response = await api_client.post(
            f"/boards/{board_id}/articles/99999/comments",
            json={"content": "댓글"},
            headers=member_headers,
        )
        assert response.status_code == 404

    async def test_unauthenticated(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
    ):
        response = await api_client.post(
            f"/boards/{board_id}/articles/{article_id}/comments",
            json={"content": "댓글"},
        )
        assert response.status_code == 422

    async def test_rate_limit(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        await api_client.post(
            f"/boards/{board_id}/articles/{article_id}/comments",
            json={"content": "첫번째 댓글"},
            headers=member_headers,
        )
        response = await api_client.post(
            f"/boards/{board_id}/articles/{article_id}/comments",
            json={"content": "두번째 댓글"},
            headers=member_headers,
        )
        assert response.status_code == 429


class TestEditComment:
    async def _create_comment(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ) -> int:
        response = await api_client.post(
            f"/boards/{board_id}/articles/{article_id}/comments",
            json={"content": "수정 전 댓글"},
            headers=member_headers,
        )
        assert response.status_code == 201
        return response.json()["id"]

    async def test_success(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
        member: dict,
        db_session: AsyncSession,
    ):
        # Valkey rate limit 우회를 위해 DB에 직접 삽입 (API 호출 없음)
        from ch04.models.comment import Comment

        comment = Comment(
            content="수정 전 댓글",
            author_id=member["id"],
            article_id=article_id,
        )
        db_session.add(comment)
        await db_session.flush()
        comment_id = comment.id

        response = await api_client.put(
            f"/boards/{board_id}/articles/{article_id}/comments/{comment_id}",
            json={"content": "수정된 댓글"},
            headers=member_headers,
        )
        assert response.status_code == 200
        assert response.json()["content"] == "수정된 댓글"

    async def test_no_permission(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
        admin_headers: dict,
    ):
        comment_id = await self._create_comment(
            api_client, board_id, article_id, member_headers
        )
        response = await api_client.put(
            f"/boards/{board_id}/articles/{article_id}/comments/{comment_id}",
            json={"content": "무단 수정"},
            headers=admin_headers,
        )
        assert response.status_code == 403

    async def test_not_found(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        response = await api_client.put(
            f"/boards/{board_id}/articles/{article_id}/comments/99999",
            json={"content": "수정"},
            headers=member_headers,
        )
        assert response.status_code == 404

    async def test_rate_limit(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        comment_id = await self._create_comment(
            api_client, board_id, article_id, member_headers
        )
        # Valkey 기반: comment_write와 comment_edit 키가 분리됨
        # 첫 번째 수정 성공 → comment_edit 키 설정
        await api_client.put(
            f"/boards/{board_id}/articles/{article_id}/comments/{comment_id}",
            json={"content": "첫 수정"},
            headers=member_headers,
        )
        # 두 번째 수정 → comment_edit 키 존재 → 429
        response = await api_client.put(
            f"/boards/{board_id}/articles/{article_id}/comments/{comment_id}",
            json={"content": "연속 수정"},
            headers=member_headers,
        )
        assert response.status_code == 429


class TestDeleteComment:
    async def _create_comment(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ) -> int:
        response = await api_client.post(
            f"/boards/{board_id}/articles/{article_id}/comments",
            json={"content": "삭제할 댓글"},
            headers=member_headers,
        )
        assert response.status_code == 201
        return response.json()["id"]

    async def test_success(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
        member: dict,
        db_session: AsyncSession,
    ):
        # Valkey rate limit 우회를 위해 DB에 직접 삽입 (API 호출 없음)
        from ch04.models.comment import Comment

        comment = Comment(
            content="삭제할 댓글",
            author_id=member["id"],
            article_id=article_id,
        )
        db_session.add(comment)
        await db_session.flush()
        comment_id = comment.id

        response = await api_client.delete(
            f"/boards/{board_id}/articles/{article_id}/comments/{comment_id}",
            headers=member_headers,
        )
        assert response.status_code == 200

        article_response = await api_client.get(
            f"/boards/{board_id}/articles/{article_id}"
        )
        assert article_response.status_code == 200
        assert len(article_response.json()["comments"]) == 0

    async def test_no_permission(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
        admin_headers: dict,
    ):
        comment_id = await self._create_comment(
            api_client, board_id, article_id, member_headers
        )
        response = await api_client.delete(
            f"/boards/{board_id}/articles/{article_id}/comments/{comment_id}",
            headers=admin_headers,
        )
        assert response.status_code == 403

    async def test_not_found(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        response = await api_client.delete(
            f"/boards/{board_id}/articles/{article_id}/comments/99999",
            headers=member_headers,
        )
        assert response.status_code == 404
