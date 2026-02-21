import httpx
from sqlalchemy.ext.asyncio import AsyncSession


class TestWriteArticle:
    async def test_success(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member_headers: dict,
    ):
        response = await api_client.post(
            f"/boards/{board_id}/articles",
            json={"title": "테스트 게시글", "content": "테스트 내용"},
            headers=member_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "테스트 게시글"
        assert data["content"] == "테스트 내용"
        assert data["board_id"] == board_id
        assert data["is_deleted"] is False

    async def test_board_not_found(
        self, api_client: httpx.AsyncClient, member_headers: dict
    ):
        response = await api_client.post(
            "/boards/99999/articles",
            json={"title": "제목", "content": "내용"},
            headers=member_headers,
        )
        assert response.status_code == 404

    async def test_unauthenticated(self, api_client: httpx.AsyncClient, board_id: int):
        response = await api_client.post(
            f"/boards/{board_id}/articles",
            json={"title": "제목", "content": "내용"},
        )
        assert response.status_code == 422

    async def test_rate_limit(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member_headers: dict,
    ):
        await api_client.post(
            f"/boards/{board_id}/articles",
            json={"title": "첫번째", "content": "내용"},
            headers=member_headers,
        )
        response = await api_client.post(
            f"/boards/{board_id}/articles",
            json={"title": "두번째", "content": "내용"},
            headers=member_headers,
        )
        assert response.status_code == 429


class TestGetArticles:
    async def test_empty_board(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ):
        """빈 게시판 조회 시 빈 목록을 반환합니다."""
        from ch02.models.board import Board

        board = Board(title="빈 게시판", description="빈 게시판 설명")
        db_session.add(board)
        await db_session.flush()

        response = await api_client.get(f"/boards/{board.id}/articles")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_articles(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        member_headers: dict,
    ):
        """게시글이 있는 게시판 조회 시 목록을 반환합니다."""
        from ch02.models.board import Board

        board = Board(title="새 게시판", description="새 게시판 설명")
        db_session.add(board)
        await db_session.flush()
        new_board_id = board.id

        await api_client.post(
            f"/boards/{new_board_id}/articles",
            json={"title": "게시글1", "content": "내용1"},
            headers=member_headers,
        )
        response = await api_client.get(f"/boards/{new_board_id}/articles")
        assert response.status_code == 200
        articles = response.json()
        assert len(articles) == 1
        assert articles[0]["title"] == "게시글1"

    async def test_pagination_last_id(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member: dict,
        db_session: AsyncSession,
    ):
        """last_id 기준으로 이전 페이지(오래된 글)를 조회합니다."""
        from sqlalchemy import select

        from ch02.models.article import Article

        for i in range(3):
            db_session.add(
                Article(
                    title=f"게시글{i + 1}",
                    content="내용",
                    author_id=member["id"],
                    board_id=board_id,
                )
            )
        await db_session.flush()
        result = await db_session.scalars(
            select(Article).where(Article.board_id == board_id).order_by(Article.id)
        )
        ids = [a.id for a in result.all()]

        response = await api_client.get(
            f"/boards/{board_id}/articles?last_id={ids[-1]}"
        )
        assert response.status_code == 200
        articles = response.json()
        assert all(a["id"] < ids[-1] for a in articles)

    async def test_pagination_first_id(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member: dict,
        db_session: AsyncSession,
    ):
        """first_id 기준으로 이후 페이지(최신 글)를 조회합니다."""
        from sqlalchemy import select

        from ch02.models.article import Article

        for i in range(3):
            db_session.add(
                Article(
                    title=f"게시글{i + 1}",
                    content="내용",
                    author_id=member["id"],
                    board_id=board_id,
                )
            )
        await db_session.flush()
        result = await db_session.scalars(
            select(Article).where(Article.board_id == board_id).order_by(Article.id)
        )
        ids = [a.id for a in result.all()]

        response = await api_client.get(
            f"/boards/{board_id}/articles?first_id={ids[0]}"
        )
        assert response.status_code == 200
        articles = response.json()
        assert all(a["id"] > ids[0] for a in articles)

    async def test_limit_10(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member: dict,
        db_session: AsyncSession,
    ):
        """최대 10개까지만 반환합니다."""
        from ch02.models.article import Article

        for i in range(12):
            db_session.add(
                Article(
                    title=f"게시글{i + 1}",
                    content="내용",
                    author_id=member["id"],
                    board_id=board_id,
                )
            )
        await db_session.flush()

        response = await api_client.get(f"/boards/{board_id}/articles")
        assert response.status_code == 200
        assert len(response.json()) == 10


class TestGetArticle:
    async def test_success_with_comments(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        db_session: AsyncSession,
    ):
        # 댓글 직접 삽입 (댓글 작성 rate limit 우회)
        from ch02.models.comment import Comment

        db_session.add(
            Comment(content="테스트 댓글", author_id=1, article_id=article_id)
        )
        await db_session.flush()

        response = await api_client.get(f"/boards/{board_id}/articles/{article_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == article_id
        assert len(data["comments"]) == 1
        assert data["comments"][0]["content"] == "테스트 댓글"

    async def test_not_found(self, api_client: httpx.AsyncClient, board_id: int):
        response = await api_client.get(f"/boards/{board_id}/articles/99999")
        assert response.status_code == 404

    async def test_wrong_board(
        self,
        api_client: httpx.AsyncClient,
        article_id: int,
    ):
        """다른 게시판의 article_id로 조회 시 404를 반환합니다."""
        response = await api_client.get(f"/boards/99999/articles/{article_id}")
        assert response.status_code == 404


class TestSearchArticles:
    async def test_search_by_content(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member: dict,
        db_session: AsyncSession,
    ):
        """OpenSearch content 필드 키워드 검색이 동작합니다."""
        from ch02.dependencies.opensearch import _client as os_client
        from ch02.models.article import Article

        # DB에 직접 삽입 후 OpenSearch에도 인덱싱
        article = Article(
            title="파이썬 게시글",
            content="파이썬과 FastAPI 를 사용한 게시판",
            author_id=member["id"],
            board_id=board_id,
        )
        db_session.add(article)
        await db_session.flush()
        await db_session.refresh(article)
        article_id = article.id

        await os_client.index(
            index="article",
            id=str(article_id),
            body={
                "title": "파이썬 게시글",
                "content": "파이썬과 FastAPI 를 사용한 게시판",
                "board_id": board_id,
                "author_id": member["id"],
            },
            refresh=True,
        )

        response = await api_client.get(
            f"/boards/{board_id}/articles/search?keyword=FastAPI"
        )
        assert response.status_code == 200
        results = response.json()
        assert any(a["id"] == article_id for a in results)

    async def test_search_no_results(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
    ):
        """검색 결과가 없을 때 빈 배열을 반환합니다."""
        response = await api_client.get(
            f"/boards/{board_id}/articles/search?keyword=존재하지않는키워드xyz"
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_search_missing_keyword(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
    ):
        """keyword 파라미터가 없으면 422를 반환합니다."""
        response = await api_client.get(f"/boards/{board_id}/articles/search")
        assert response.status_code == 422


class TestEditArticle:
    async def test_success(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        response = await api_client.put(
            f"/boards/{board_id}/articles/{article_id}",
            json={"title": "수정된 제목", "content": "수정된 내용"},
            headers=member_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "수정된 제목"
        assert data["content"] == "수정된 내용"

    async def test_partial_edit(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        """title만 수정하면 content는 변경되지 않습니다."""
        response = await api_client.put(
            f"/boards/{board_id}/articles/{article_id}",
            json={"title": "제목만 수정"},
            headers=member_headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "제목만 수정"
        assert response.json()["content"] == "테스트 내용"

    async def test_no_changes(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        """title, content 모두 없으면 변경 없이 현재 데이터를 반환합니다."""
        response = await api_client.put(
            f"/boards/{board_id}/articles/{article_id}",
            json={},
            headers=member_headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "테스트 게시글"

    async def test_no_permission(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        admin_headers: dict,
    ):
        """게시글 작성자가 아니면 수정할 수 없습니다."""
        response = await api_client.put(
            f"/boards/{board_id}/articles/{article_id}",
            json={"title": "무단 수정"},
            headers=admin_headers,
        )
        assert response.status_code == 403

    async def test_not_found(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member_headers: dict,
    ):
        response = await api_client.put(
            f"/boards/{board_id}/articles/99999",
            json={"title": "수정"},
            headers=member_headers,
        )
        assert response.status_code == 404


class TestDeleteArticle:
    async def test_success(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        member_headers: dict,
    ):
        response = await api_client.delete(
            f"/boards/{board_id}/articles/{article_id}",
            headers=member_headers,
        )
        assert response.status_code == 200

        # 삭제 후 조회 시 404
        get_response = await api_client.get(f"/boards/{board_id}/articles/{article_id}")
        assert get_response.status_code == 404

    async def test_no_permission(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        article_id: int,
        admin_headers: dict,
    ):
        response = await api_client.delete(
            f"/boards/{board_id}/articles/{article_id}",
            headers=admin_headers,
        )
        assert response.status_code == 403

    async def test_not_found(
        self,
        api_client: httpx.AsyncClient,
        board_id: int,
        member_headers: dict,
    ):
        response = await api_client.delete(
            f"/boards/{board_id}/articles/99999",
            headers=member_headers,
        )
        assert response.status_code == 404
