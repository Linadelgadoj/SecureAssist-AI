import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app

ORIGIN = "http://localhost:5173"


def make_settings(**overrides):
    values = dict(
        app_env="development", cors_origins=[ORIGIN], frontend_origin=ORIGIN,
        supabase_url="", supabase_publishable_key="",
        supabase_auth_callback_url="http://testserver/api/v1/auth/google/callback",
        frontend_auth_success_url=f"{ORIGIN}/", auth_cookie_secure=False,
        auth_cookie_name="secureassist_refresh", auth_cookie_domain=None,
        auth_cookie_max_age_seconds=None, dev_login=True,
    )
    values.update(overrides)
    return Settings(**values)


def login(client: TestClient) -> str:
    start = client.get("/api/v1/auth/google/start", follow_redirects=False)
    assert start.status_code == 302
    callback = client.get(start.headers["location"], follow_redirects=False)
    assert callback.status_code == 303
    assert callback.headers["location"] == f"{ORIGIN}/"
    session = client.get("/api/v1/auth/session", headers={"Origin": ORIGIN})
    body = session.json()
    assert body["authenticated"] is True
    assert body["user"]["email"] == "dev@localhost"
    return body["access_token"]


def test_dev_login_allows_full_conversation_flow_without_supabase():
    client = TestClient(create_app(make_settings()))
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/v1/conversations", json={"title": "Cámara sin video"}, headers=headers)
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    sent = client.post(f"/api/v1/conversations/{conversation_id}/messages",
                       json={"content_text": "El DVR no muestra el canal 3"}, headers=headers)
    assert sent.status_code == 201

    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers).json()
    assert [m["content_text"] for m in messages["items"]] == ["El DVR no muestra el canal 3"]
    assert len(client.get("/api/v1/conversations", headers=headers).json()["items"]) == 1


def test_dev_login_rejects_unknown_tokens_and_logout_ends_session():
    client = TestClient(create_app(make_settings()))
    assert client.get("/api/v1/conversations", headers={"Authorization": "Bearer inventado"}).status_code == 401
    login(client)
    assert client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code == 204
    assert client.get("/api/v1/auth/session", headers={"Origin": ORIGIN}).json()["authenticated"] is False


def test_dev_login_callback_requires_matching_state_cookie():
    client = TestClient(create_app(make_settings()))
    response = client.get("/api/v1/auth/google/callback?code=dev&state=falso", follow_redirects=False)
    assert "auth_error" in response.headers["location"]


def test_dev_login_is_refused_outside_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("DEV_LOGIN", "true")
    with pytest.raises(ValueError):
        get_settings()
    with pytest.raises(ValueError):
        create_app(make_settings(app_env="production"))


def test_dev_login_is_off_by_default():
    client = TestClient(create_app(make_settings(dev_login=False)))
    assert client.app.state.auth_service is None
