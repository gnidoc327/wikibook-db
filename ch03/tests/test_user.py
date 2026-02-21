import httpx


class TestSignUp:
    async def test_success(self, api_client: httpx.AsyncClient):
        response = await api_client.post(
            "/users/sign-up",
            json={
                "username": "newuser",
                "email": "newuser@test.com",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "member"
        assert "id" in data

    async def test_duplicate_username(self, api_client: httpx.AsyncClient):
        await api_client.post(
            "/users/sign-up",
            json={"username": "dup", "email": "dup1@test.com", "password": "pw"},
        )
        response = await api_client.post(
            "/users/sign-up",
            json={"username": "dup", "email": "dup2@test.com", "password": "pw"},
        )
        assert response.status_code == 409

    async def test_duplicate_email(self, api_client: httpx.AsyncClient):
        await api_client.post(
            "/users/sign-up",
            json={"username": "user1", "email": "same@test.com", "password": "pw"},
        )
        response = await api_client.post(
            "/users/sign-up",
            json={"username": "user2", "email": "same@test.com", "password": "pw"},
        )
        assert response.status_code == 409


class TestLogin:
    async def test_success(self, api_client: httpx.AsyncClient):
        await api_client.post(
            "/users/sign-up",
            json={
                "username": "loginuser",
                "email": "login@test.com",
                "password": "password123",
            },
        )
        response = await api_client.post(
            "/users/login",
            json={"username": "loginuser", "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_wrong_password(self, api_client: httpx.AsyncClient):
        await api_client.post(
            "/users/sign-up",
            json={
                "username": "loginuser2",
                "email": "login2@test.com",
                "password": "correct",
            },
        )
        response = await api_client.post(
            "/users/login",
            json={"username": "loginuser2", "password": "wrong"},
        )
        assert response.status_code == 401

    async def test_unknown_user(self, api_client: httpx.AsyncClient):
        response = await api_client.post(
            "/users/login",
            json={"username": "nobody", "password": "password"},
        )
        assert response.status_code == 401


class TestGetUsers:
    async def test_authenticated(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        response = await api_client.get("/users", headers=admin_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_unauthenticated(self, api_client: httpx.AsyncClient):
        response = await api_client.get("/users")
        assert response.status_code == 422


class TestDeleteUser:
    async def test_delete_own_user(self, api_client: httpx.AsyncClient, member: dict):
        response = await api_client.delete(
            f"/users/{member['id']}", headers=member["headers"]
        )
        assert response.status_code == 204

    async def test_admin_can_delete_other_user(
        self, api_client: httpx.AsyncClient, admin_headers: dict, member: dict
    ):
        response = await api_client.delete(
            f"/users/{member['id']}", headers=admin_headers
        )
        assert response.status_code == 204

    async def test_member_cannot_delete_other_user(
        self, api_client: httpx.AsyncClient, admin_headers: dict, member: dict
    ):
        users = (await api_client.get("/users", headers=admin_headers)).json()
        admin_user = next(u for u in users if u["username"] == "admin")

        response = await api_client.delete(
            f"/users/{admin_user['id']}", headers=member["headers"]
        )
        assert response.status_code == 403

    async def test_delete_nonexistent_user(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        response = await api_client.delete("/users/99999", headers=admin_headers)
        assert response.status_code == 404

    async def test_delete_already_deleted_user(
        self, api_client: httpx.AsyncClient, member: dict
    ):
        await api_client.delete(f"/users/{member['id']}", headers=member["headers"])
        from ch03.config.config import settings

        login = await api_client.post(
            "/users/login",
            json={
                "username": settings.admin.username,
                "password": settings.admin.password,
            },
        )
        admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        response = await api_client.delete(
            f"/users/{member['id']}", headers=admin_headers
        )
        assert response.status_code == 404


class TestLogout:
    async def test_success(self, api_client: httpx.AsyncClient, member_headers: dict):
        response = await api_client.post("/users/logout", headers=member_headers)
        assert response.status_code == 200
        assert response.json() == "ok"

    async def test_unauthenticated(self, api_client: httpx.AsyncClient):
        response = await api_client.post("/users/logout")
        assert response.status_code == 422


class TestLogoutAll:
    async def test_success(self, api_client: httpx.AsyncClient, member_headers: dict):
        response = await api_client.post("/users/logout/all", headers=member_headers)
        assert response.status_code == 200
        assert response.json() == "ok"

    async def test_token_revoked_after_logout(
        self, api_client: httpx.AsyncClient, member_headers: dict
    ):
        await api_client.post("/users/logout/all", headers=member_headers)
        # Valkey 블랙리스트에 등록된 토큰으로 재요청 → 401
        response = await api_client.get("/users", headers=member_headers)
        assert response.status_code == 401

    async def test_second_call_with_revoked_token_returns_401(
        self, api_client: httpx.AsyncClient, member_headers: dict
    ):
        await api_client.post("/users/logout/all", headers=member_headers)
        response = await api_client.post("/users/logout/all", headers=member_headers)
        assert response.status_code == 401


class TestTokenValidation:
    async def test_valid_token(
        self, api_client: httpx.AsyncClient, member_headers: dict
    ):
        response = await api_client.post(
            "/users/token/validation", headers=member_headers
        )
        assert response.status_code == 200
        assert response.json() == "ok"

    async def test_revoked_token(
        self, api_client: httpx.AsyncClient, member_headers: dict
    ):
        await api_client.post("/users/logout/all", headers=member_headers)
        response = await api_client.post(
            "/users/token/validation", headers=member_headers
        )
        assert response.status_code == 403

    async def test_invalid_token(self, api_client: httpx.AsyncClient):
        headers = {"Authorization": "Bearer invalid.token.value"}
        response = await api_client.post("/users/token/validation", headers=headers)
        assert response.status_code == 403

    async def test_missing_bearer_scheme(self, api_client: httpx.AsyncClient):
        headers = {"Authorization": "Basic somevalue"}
        response = await api_client.post("/users/token/validation", headers=headers)
        assert response.status_code == 401


class TestUpdateRole:
    async def test_admin_can_promote_to_admin(
        self, api_client: httpx.AsyncClient, admin_headers: dict, member: dict
    ):
        response = await api_client.patch(
            f"/users/{member['id']}/role",
            json={"role": "admin"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"

    async def test_admin_can_demote_to_member(
        self, api_client: httpx.AsyncClient, admin_headers: dict, member: dict
    ):
        await api_client.patch(
            f"/users/{member['id']}/role",
            json={"role": "admin"},
            headers=admin_headers,
        )
        response = await api_client.patch(
            f"/users/{member['id']}/role",
            json={"role": "member"},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["role"] == "member"

    async def test_member_cannot_change_role(
        self, api_client: httpx.AsyncClient, admin_headers: dict, member: dict
    ):
        users = (await api_client.get("/users", headers=admin_headers)).json()
        admin_user = next(u for u in users if u["username"] == "admin")

        response = await api_client.patch(
            f"/users/{admin_user['id']}/role",
            json={"role": "member"},
            headers=member["headers"],
        )
        assert response.status_code == 403

    async def test_update_role_nonexistent_user(
        self, api_client: httpx.AsyncClient, admin_headers: dict
    ):
        response = await api_client.patch(
            "/users/99999/role",
            json={"role": "admin"},
            headers=admin_headers,
        )
        assert response.status_code == 404
