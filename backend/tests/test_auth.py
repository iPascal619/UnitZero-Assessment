"""Tests for authentication and authorization rules.

Covers:
- Login with valid/invalid credentials
- Access control: unauthenticated requests blocked
- Role-based access: clients can't access operator endpoints and vice versa
- Admin-only endpoints
- Deactivated user cannot authenticate
"""


class TestLogin:
    def test_login_valid(self, client, client_user):
        resp = client.post(
            "/api/auth/login",
            json={"username": "client1", "password": "testpass123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, client_user):
        resp = client.post(
            "/api/auth/login",
            json={"username": "client1", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_login_inactive_user(self, client, db, client_user):
        client_user.is_active = False
        db.commit()
        resp = client.post(
            "/api/auth/login",
            json={"username": "client1", "password": "testpass123"},
        )
        assert resp.status_code == 403


class TestUnauthenticatedAccess:
    def test_requests_require_auth(self, client):
        resp = client.get("/api/requests")
        assert resp.status_code == 403

    def test_episodes_require_auth(self, client):
        resp = client.get("/api/episodes")
        assert resp.status_code == 403

    def test_users_require_auth(self, client):
        resp = client.get("/api/users")
        assert resp.status_code == 403


class TestRoleAuthorization:
    def test_client_cannot_list_episodes(self, client, client_headers):
        resp = client.get("/api/episodes", headers=client_headers)
        assert resp.status_code == 403

    def test_client_cannot_import_episodes(self, client, client_headers):
        resp = client.post(
            "/api/episodes/import",
            headers=client_headers,
            files={"file": ("test.csv", b"episode_id\nEP-001", "text/csv")},
        )
        assert resp.status_code == 403

    def test_operator_cannot_create_users(self, client, operator_headers):
        resp = client.post(
            "/api/users",
            headers=operator_headers,
            json={
                "username": "newuser",
                "email": "new@test.com",
                "password": "pass123456",
                "role": "client",
            },
        )
        assert resp.status_code == 403

    def test_operator_cannot_create_request(self, client, operator_headers):
        resp = client.post(
            "/api/requests",
            headers=operator_headers,
            json={
                "task_name": "picking_cups",
                "episodes_requested": 10,
                "deadline": "2025-12-31",
            },
        )
        assert resp.status_code == 403

    def test_admin_can_create_users(self, client, admin_headers):
        resp = client.post(
            "/api/users",
            headers=admin_headers,
            json={
                "username": "newuser",
                "email": "new@test.com",
                "password": "pass123456",
                "role": "client",
            },
        )
        assert resp.status_code == 201

    def test_admin_can_list_users(self, client, admin_headers):
        resp = client.get("/api/users", headers=admin_headers)
        assert resp.status_code == 200


class TestClientIsolation:
    """Clients should only see their own requests."""

    def test_client_sees_only_own_requests(
        self, client, client_headers, client2_headers, client_user, client_user2
    ):
        # Client 1 creates a request
        resp1 = client.post(
            "/api/requests",
            headers=client_headers,
            json={
                "task_name": "picking_cups",
                "episodes_requested": 5,
                "deadline": "2025-12-31",
            },
        )
        assert resp1.status_code == 201

        # Client 2 creates a request
        resp2 = client.post(
            "/api/requests",
            headers=client2_headers,
            json={
                "task_name": "stacking_blocks",
                "episodes_requested": 3,
                "deadline": "2025-12-31",
            },
        )
        assert resp2.status_code == 201

        # Client 1 sees only their request
        resp = client.get("/api/requests", headers=client_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["task_name"] == "picking_cups"

        # Client 2 sees only their request
        resp = client.get("/api/requests", headers=client2_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["task_name"] == "stacking_blocks"

    def test_client_cannot_view_other_client_request(
        self, client, client_headers, client2_headers
    ):
        # Client 1 creates a request
        resp = client.post(
            "/api/requests",
            headers=client_headers,
            json={
                "task_name": "picking_cups",
                "episodes_requested": 5,
                "deadline": "2025-12-31",
            },
        )
        request_id = resp.json()["id"]

        # Client 2 tries to view it
        resp = client.get(
            f"/api/requests/{request_id}", headers=client2_headers
        )
        assert resp.status_code == 403
