from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession


class TestWriteAd:
    async def test_success(self, api_client: httpx.AsyncClient, admin_headers: dict):
        response = await api_client.post(
            "/ads",
            json={"title": "테스트 광고", "content": "광고 내용"},
            headers=admin_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "테스트 광고"
        assert data["content"] == "광고 내용"
        assert data["is_visible"] is True
        assert data["is_deleted"] is False

    async def test_member_cannot_write(
        self, api_client: httpx.AsyncClient, member_headers: dict
    ):
        """일반 회원은 광고를 등록할 수 없습니다."""
        response = await api_client.post(
            "/ads",
            json={"title": "광고", "content": "내용"},
            headers=member_headers,
        )
        assert response.status_code == 403

    async def test_unauthenticated(self, api_client: httpx.AsyncClient):
        response = await api_client.post(
            "/ads",
            json={"title": "광고", "content": "내용"},
        )
        assert response.status_code == 422


class TestGetAds:
    async def test_empty_list(self, api_client: httpx.AsyncClient):
        response = await api_client.get("/ads")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_ads(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        await api_client.post(
            "/ads",
            json={"title": "광고1", "content": "내용1"},
            headers=admin_headers,
        )
        response = await api_client.get("/ads")
        assert response.status_code == 200
        ads = response.json()
        assert len(ads) == 1
        assert ads[0]["title"] == "광고1"


class TestGetAd:
    async def test_success_from_db(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        """광고 단건 조회 - DB에서 가져오고 Valkey에 캐싱됩니다."""
        create_resp = await api_client.post(
            "/ads",
            json={"title": "단건 광고", "content": "내용"},
            headers=admin_headers,
        )
        assert create_resp.status_code == 201
        ad_id = create_resp.json()["id"]

        # write_ad에서 이미 Valkey에 캐싱됨 → 여기서도 캐시 히트
        response = await api_client.get(f"/ads/{ad_id}")
        assert response.status_code == 200
        assert response.json()["id"] == ad_id
        assert response.json()["title"] == "단건 광고"

    async def test_valkey_cache_hit(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        """두 번 조회해도 동일한 결과를 반환합니다 (Valkey 캐시 히트)."""
        create_resp = await api_client.post(
            "/ads",
            json={"title": "캐시 광고", "content": "내용"},
            headers=admin_headers,
        )
        ad_id = create_resp.json()["id"]

        response1 = await api_client.get(f"/ads/{ad_id}")
        response2 = await api_client.get(f"/ads/{ad_id}")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json()["id"] == response2.json()["id"]
        assert response1.json()["title"] == response2.json()["title"]

    async def test_valkey_cache_populated_after_db_read(
        self,
        api_client: httpx.AsyncClient,
        admin_headers: dict,
        db_session: AsyncSession,
    ):
        """Valkey 캐시가 없을 때 DB에서 조회 후 Valkey에 저장됩니다."""
        from ch05.dependencies.valkey import _client as valkey_client
        from ch05.models.advertisement import Advertisement

        # DB에 직접 삽입 (Valkey 캐시 없음)
        ad = Advertisement(title="DB 전용 광고", content="내용")
        db_session.add(ad)
        await db_session.flush()
        await db_session.refresh(ad)
        ad_id = ad.id

        # 캐시 없음 확인
        cached = await valkey_client.get(f"ad:{ad_id}")
        assert cached is None

        # 조회 → DB에서 가져오고 Valkey에 저장
        response = await api_client.get(f"/ads/{ad_id}")
        assert response.status_code == 200

        # 이후 Valkey에 캐싱됨
        cached = await valkey_client.get(f"ad:{ad_id}")
        assert cached is not None

    async def test_not_found(self, api_client: httpx.AsyncClient):
        response = await api_client.get("/ads/99999")
        assert response.status_code == 404

    async def test_records_view_history_in_mongodb(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        """광고 조회 시 MongoDB adViewHistory 컬렉션에 기록됩니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        create_resp = await api_client.post(
            "/ads",
            json={"title": "히스토리 광고", "content": "내용"},
            headers=admin_headers,
        )
        ad_id = create_resp.json()["id"]

        await api_client.get(f"/ads/{ad_id}")

        count = await mongo_db["adViewHistory"].count_documents({"ad_id": ad_id})
        assert count == 1

    async def test_view_history_with_authenticated_user(
        self,
        api_client: httpx.AsyncClient,
        admin_headers: dict,
        member_headers: dict,
        member: dict,
    ):
        """인증된 사용자의 조회 기록에는 username이 포함됩니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        create_resp = await api_client.post(
            "/ads",
            json={"title": "인증 히스토리 광고", "content": "내용"},
            headers=admin_headers,
        )
        ad_id = create_resp.json()["id"]

        await api_client.get(f"/ads/{ad_id}", headers=member_headers)

        doc = await mongo_db["adViewHistory"].find_one({"ad_id": ad_id})
        assert doc is not None
        assert doc["username"] == member["username"]

    async def test_view_history_anonymous_user(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        """익명 사용자의 조회 기록에는 username이 None입니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        create_resp = await api_client.post(
            "/ads",
            json={"title": "익명 히스토리 광고", "content": "내용"},
            headers=admin_headers,
        )
        ad_id = create_resp.json()["id"]

        # 인증 없이 조회
        await api_client.get(f"/ads/{ad_id}")

        doc = await mongo_db["adViewHistory"].find_one({"ad_id": ad_id})
        assert doc is not None
        assert doc["username"] is None


class TestClickAd:
    async def test_success(self, api_client: httpx.AsyncClient, admin_headers: dict):
        """광고 클릭 기록이 MongoDB adClickHistory 컬렉션에 저장됩니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        create_resp = await api_client.post(
            "/ads",
            json={"title": "클릭 광고", "content": "내용"},
            headers=admin_headers,
        )
        ad_id = create_resp.json()["id"]

        response = await api_client.post(f"/ads/{ad_id}/click")
        assert response.status_code == 200
        assert response.json() == "click"

        count = await mongo_db["adClickHistory"].count_documents({"ad_id": ad_id})
        assert count == 1

    async def test_click_not_found(self, api_client: httpx.AsyncClient):
        response = await api_client.post("/ads/99999/click")
        assert response.status_code == 404

    async def test_click_with_authenticated_user(
        self,
        api_client: httpx.AsyncClient,
        admin_headers: dict,
        member_headers: dict,
        member: dict,
    ):
        """인증된 사용자의 클릭 기록에는 username이 포함됩니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        create_resp = await api_client.post(
            "/ads",
            json={"title": "인증 클릭 광고", "content": "내용"},
            headers=admin_headers,
        )
        ad_id = create_resp.json()["id"]

        await api_client.post(f"/ads/{ad_id}/click", headers=member_headers)

        doc = await mongo_db["adClickHistory"].find_one({"ad_id": ad_id})
        assert doc is not None
        assert doc["username"] == member["username"]


class TestAdViewHistory:
    async def test_empty_history(self, api_client: httpx.AsyncClient):
        """어제 히스토리가 없으면 빈 배열을 반환합니다."""
        response = await api_client.get("/ads/history/view")
        assert response.status_code == 200
        assert response.json() == []

    async def test_history_aggregation(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        """MongoDB에 어제 날짜 데이터를 직접 삽입하면 집계 결과에 포함됩니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        yesterday_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        ) - timedelta(days=1)

        # 어제 날짜로 직접 삽입 (로그인 유저 2명, 익명 1명)
        await mongo_db["adViewHistory"].insert_many(
            [
                {
                    "ad_id": 999,
                    "username": "user1",
                    "client_ip": "1.2.3.4",
                    "is_true_view": True,
                    "created_date": yesterday_start,
                },
                {
                    "ad_id": 999,
                    "username": "user2",
                    "client_ip": "1.2.3.5",
                    "is_true_view": True,
                    "created_date": yesterday_start,
                },
                {
                    "ad_id": 999,
                    "username": None,
                    "client_ip": "1.2.3.6",
                    "is_true_view": False,
                    "created_date": yesterday_start,
                },
            ]
        )

        response = await api_client.get("/ads/history/view")
        assert response.status_code == 200
        results = response.json()
        ad_result = next((r for r in results if r["ad_id"] == 999), None)
        assert ad_result is not None
        assert ad_result["count"] == 3


class TestAdClickHistory:
    async def test_empty_history(self, api_client: httpx.AsyncClient):
        """어제 클릭 히스토리가 없으면 빈 배열을 반환합니다."""
        response = await api_client.get("/ads/history/click")
        assert response.status_code == 200
        assert response.json() == []

    async def test_history_aggregation(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        """MongoDB에 어제 날짜 클릭 데이터를 직접 삽입하면 집계 결과에 포함됩니다."""
        from ch05.dependencies.mongodb import _database as mongo_db

        yesterday_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        ) - timedelta(days=1)

        # 중복 포함 (같은 user1이 2번 클릭 → unique 1명으로 집계)
        await mongo_db["adClickHistory"].insert_many(
            [
                {
                    "ad_id": 888,
                    "username": "user1",
                    "client_ip": "1.2.3.4",
                    "created_date": yesterday_start,
                },
                {
                    "ad_id": 888,
                    "username": "user1",
                    "client_ip": "1.2.3.4",
                    "created_date": yesterday_start,
                },
                {
                    "ad_id": 888,
                    "username": None,
                    "client_ip": "9.8.7.6",
                    "created_date": yesterday_start,
                },
            ]
        )

        response = await api_client.get("/ads/history/click")
        assert response.status_code == 200
        results = response.json()
        ad_result = next((r for r in results if r["ad_id"] == 888), None)
        assert ad_result is not None
        # user1 (unique 1) + 익명 ip (unique 1) = 2
        assert ad_result["count"] == 2
