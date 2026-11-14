from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def make_settings():
    return Settings("development", ["http://localhost:5173"], "http://localhost:5173", "https://sample.supabase.co",
                    "publishable-test", "http://localhost:8000/api/v1/auth/google/callback", "http://localhost:5173/",
                    False, "secureassist_refresh", None, None)


class FakeAuthService:
    def __init__(self):
        self.current_refresh_token = None
        self.refresh_rotations = {
            "refresh-test": "rotated-refresh",
            "rotated-refresh": "next-refresh",
        }

    class Transactions:
        def consume(self, _state):
            return type("Transaction", (), {"code_verifier": "test-verifier"})()
    transactions = Transactions()

    def start(self):
        return "state123", "https://sample.supabase.co/auth/v1/authorize?provider=google"

    def consume_state(self, state, cookie):
        if state != cookie or state != "state123":
            from app.services.auth_service import AuthRejected
            raise AuthRejected()
        return self.transactions.consume(state)

    async def exchange_and_validate(self, code, verifier):
        if code != "good-code" or verifier != "test-verifier":
            from app.services.auth_service import AuthRejected
            raise AuthRejected()
        self.current_refresh_token = "refresh-test"
        from app.schemas.auth import AuthUser
        return "access-test", "refresh-test", AuthUser(id="64de01b6-9520-4cf4-8b22-2c64af080fe7", email="user@example.com", email_verified=True), 3600

    async def renew(self, refresh):
        from app.services.auth_service import AuthRejected
        if refresh != self.current_refresh_token or refresh not in self.refresh_rotations:
            raise AuthRejected()
        rotated = self.refresh_rotations[refresh]
        self.current_refresh_token = rotated
        from app.schemas.auth import AuthUser
        return "new-access", rotated, AuthUser(id="64de01b6-9520-4cf4-8b22-2c64af080fe7", email="user@example.com", email_verified=True), 3600

    async def logout(self, _refresh):
        return None


def test_start_callback_session_refresh_logout_and_health():
    app = create_app(make_settings(), FakeAuthService())
    client = TestClient(app)
    start = client.get("/api/v1/auth/google/start", follow_redirects=False)
    assert start.status_code == 302
    assert start.headers["location"].startswith("https://sample.supabase.co")
    state_cookie = start.cookies.get("secureassist_oauth_state")
    callback = client.get(f"/api/v1/auth/google/callback?code=good-code&state={state_cookie}", follow_redirects=False)
    assert callback.status_code == 303
    assert callback.headers["location"] == "http://localhost:5173/"
    assert "access-test" not in callback.headers["location"]
    assert "refresh-test" not in callback.headers["location"]
    assert callback.cookies.get("secureassist_refresh") == "refresh-test"

    headers = {"Origin": "http://localhost:5173"}
    session = client.get("/api/v1/auth/session", headers=headers)
    assert session.status_code == 200
    assert session.json()["access_token"] == "new-access"
    assert "rotated-refresh" not in session.text
    assert session.cookies.get("secureassist_refresh") == "rotated-refresh"
    refreshed = client.post("/api/v1/auth/refresh", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.cookies.get("secureassist_refresh") == "next-refresh"
    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 204
    health = client.get("/api/v1/health")
    assert health.status_code == 200 and health.json()["status"] == "ok"


def test_cookie_endpoints_reject_invalid_origin():
    client = TestClient(create_app(make_settings(), FakeAuthService()))
    response = client.post("/api/v1/auth/refresh", headers={"Origin": "https://attacker.invalid"})
    assert response.status_code == 403


def test_callback_rejects_state_mismatch_without_session():
    client = TestClient(create_app(make_settings(), FakeAuthService()))
    response = client.get("/api/v1/auth/google/callback?code=good-code&state=bad", follow_redirects=False)
    assert response.status_code == 303
    assert "auth_error=authentication_failed" in response.headers["location"]
    assert "access_token" not in response.headers["location"]


def test_invalid_refresh_rejects_and_clears_cookie():
    client = TestClient(create_app(make_settings(), FakeAuthService()))
    client.cookies.set("secureassist_refresh", "invalid", path="/api/v1/auth")
    response = client.post("/api/v1/auth/refresh", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID"
    assert "secureassist_refresh=" in response.headers["set-cookie"]
    assert "max-age=0" in response.headers["set-cookie"].lower()

