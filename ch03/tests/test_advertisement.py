import httpx


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
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        """Valkey 캐시가 없을 때 DB에서 조회 후 Valkey에 저장됩니다."""
        from ch03.dependencies.mysql import _async_session
        from ch03.dependencies.valkey import _client as valkey_client
        from ch03.models.advertisement import Advertisement

        # DB에 직접 삽입 (Valkey 캐시 없음)
        async with _async_session() as session:
            ad = Advertisement(title="DB 전용 광고", content="내용")
            session.add(ad)
            await session.commit()
            await session.refresh(ad)
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
