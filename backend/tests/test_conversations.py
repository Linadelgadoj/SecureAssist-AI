import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import TokenValidationError
from app.main import create_app
from app.repositories.conversations import ConversationStoreUnavailable, SupabaseConversationRepository


OWNER_ID = "64de01b6-9520-4cf4-8b22-2c64af080fe7"
OTHER_OWNER_ID = "7382fdc4-b5ad-4b2e-916e-36a0c8532f17"


class FakeVerifier:
    def verify(self, token):
        owners = {"owner-token": OWNER_ID, "other-token": OTHER_OWNER_ID}
        if token not in owners:
            raise TokenValidationError("invalid token")
        return {"sub": owners[token], "email": f"{owners[token]}@example.com"}


class FakeAuthService:
    verifier = FakeVerifier()


class MemoryConversationRepository:
    def __init__(self):
        self.conversations = []
        self.messages = []
        self.fail = False

    def _check(self):
        if self.fail:
            raise ConversationStoreUnavailable()

    async def create_conversation(self, owner_user_id, title):
        self._check()
        now = datetime.now(timezone.utc).isoformat()
        row = {"id": str(uuid4()), "owner_user_id": owner_user_id, "title": title,
               "state": "open", "created_at": now, "last_activity_at": now}
        self.conversations.append(row)
        return row

    async def list_conversations(self, owner_user_id, limit, offset):
        self._check()
        rows = [row for row in self.conversations if row["owner_user_id"] == owner_user_id]
        return sorted(rows, key=lambda row: (row["last_activity_at"], row["id"]), reverse=True)[offset:offset + limit]

    async def get_conversation(self, owner_user_id, conversation_id):
        self._check()
        return next((row for row in self.conversations
                     if row["owner_user_id"] == owner_user_id and row["id"] == conversation_id), None)

    async def create_message(self, owner_user_id, conversation_id, content_text):
        self._check()
        now = datetime.now(timezone.utc).isoformat()
        row = {"id": str(uuid4()), "conversation_id": conversation_id,
               "owner_user_id": owner_user_id, "role": "installer", "content_text": content_text,
               "processing_state": "received", "created_at": now}
        self.messages.append(row)
        for conversation in self.conversations:
            if conversation["id"] == conversation_id and conversation["owner_user_id"] == owner_user_id:
                conversation["last_activity_at"] = now
        return row

    async def list_messages(self, owner_user_id, conversation_id, limit, offset):
        self._check()
        rows = [row for row in self.messages
                if row["owner_user_id"] == owner_user_id and row["conversation_id"] == conversation_id]
        return sorted(rows, key=lambda row: (row["created_at"], row["id"]))[offset:offset + limit]


@pytest.fixture
def setup_api():
    settings = Settings("development", ["http://localhost:5173"], "http://localhost:5173",
                        "https://sample.supabase.co", "publishable-test",
                        "http://localhost:8000/api/v1/auth/google/callback", "http://localhost:5173/",
                        False, "secureassist_refresh", None, None)
    repository = MemoryConversationRepository()
    app = create_app(settings, FakeAuthService())
    app.state.conversation_repository_factory = lambda _token: repository
    return TestClient(app), repository


def test_create_and_list_conversations_are_scoped_to_authenticated_user(setup_api):
    client, repository = setup_api
    own = client.post("/api/v1/conversations", headers={"Authorization": "Bearer owner-token"}, json={"title": "Cámara principal"})
    foreign = client.post("/api/v1/conversations", headers={"Authorization": "Bearer other-token"}, json={"title": "Privada de otra persona"})
    assert own.status_code == foreign.status_code == 201
    assert repository.conversations[0]["owner_user_id"] == OWNER_ID

    listed = client.get("/api/v1/conversations", headers={"Authorization": "Bearer owner-token"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [own.json()["id"]]


def test_conversation_list_cursor_returns_following_page(setup_api):
    client, _ = setup_api
    headers = {"Authorization": "Bearer owner-token"}
    created = [client.post("/api/v1/conversations", headers=headers, json={}).json()["id"] for _ in range(3)]
    first = client.get("/api/v1/conversations?limit=2", headers=headers).json()
    second = client.get(f"/api/v1/conversations?limit=2&cursor={first['next_cursor']}", headers=headers).json()
    assert len(first["items"]) == 2
    assert first["next_cursor"] is not None
    assert len(second["items"]) == 1
    assert set(created) == {item["id"] for item in first["items"] + second["items"]}
    assert client.get("/api/v1/conversations?cursor=invalid", headers=headers).status_code == 400


def test_create_conversation_rejects_owner_supplied_by_client(setup_api):
    client, _ = setup_api
    response = client.post("/api/v1/conversations", headers={"Authorization": "Bearer owner-token"},
                           json={"title": "Trabajo", "owner_user_id": OTHER_OWNER_ID})
    assert response.status_code == 422


def test_messages_can_be_saved_and_listed_for_own_conversation(setup_api):
    client, _ = setup_api
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/api/v1/conversations", headers=headers, json={}).json()
    saved = client.post(f"/api/v1/conversations/{conversation['id']}/messages", headers=headers,
                        json={"content_text": "La cámara enciende, pero no transmite imagen."})
    assert saved.status_code == 201
    assert saved.json()["role"] == "installer"
    assert saved.json()["processing_state"] == "received"

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=headers)
    assert messages.status_code == 200
    assert [item["id"] for item in messages.json()["items"]] == [saved.json()["id"]]
    assert messages.json()["items"][0]["content_text"] == "La cámara enciende, pero no transmite imagen."


def test_conversation_id_cannot_be_used_to_read_another_users_conversation(setup_api):
    client, _ = setup_api
    foreign = client.post("/api/v1/conversations", headers={"Authorization": "Bearer other-token"}, json={}).json()
    headers = {"Authorization": "Bearer owner-token"}

    assert client.get(f"/api/v1/conversations/{foreign['id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/conversations/{foreign['id']}/messages", headers=headers).status_code == 404
    assert client.post(f"/api/v1/conversations/{foreign['id']}/messages", headers=headers,
                       json={"content_text": "No debe guardarse"}).status_code == 404


def test_conversations_reject_requests_without_valid_authentication(setup_api):
    client, _ = setup_api
    assert client.get("/api/v1/conversations").status_code == 401
    assert client.post("/api/v1/conversations", headers={"Authorization": "Bearer bad-token"}, json={}).status_code == 401


def test_message_validation_rejects_blank_text_and_auth_tokens(setup_api):
    client, _ = setup_api
    headers = {"Authorization": "Bearer owner-token"}
    conversation = client.post("/api/v1/conversations", headers=headers, json={}).json()
    url = f"/api/v1/conversations/{conversation['id']}/messages"
    assert client.post(url, headers=headers, json={"content_text": "   "}).status_code == 422
    assert client.post(url, headers=headers, json={"content_text": "Bearer abcdefghijklmnopqrstuvwxyz"}).status_code == 422


def test_persistence_unavailable_returns_safe_service_error(setup_api):
    client, repository = setup_api
    repository.fail = True
    response = client.get("/api/v1/conversations", headers={"Authorization": "Bearer owner-token"})
    assert response.status_code == 503
    assert "INTERNAL_ERROR" not in response.text
    assert "no está disponible temporalmente" in response.text


def test_supabase_repository_forwards_user_jwt_and_owner_filter(monkeypatch):
    captured = {}

    class StubAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, **kwargs)
            return httpx.Response(200, json=[])

    monkeypatch.setattr("app.repositories.conversations.httpx.AsyncClient", StubAsyncClient)
    settings = Settings("development", [], "http://localhost:5173", "https://sample.supabase.co",
                        "publishable-test", "http://localhost:8000/callback", "http://localhost:5173/",
                        False, "secureassist_refresh", None, None)
    repository = SupabaseConversationRepository(settings, "user-access-jwt")
    asyncio.run(repository.list_conversations(OWNER_ID, 20, 0))

    assert captured["url"] == "https://sample.supabase.co/rest/v1/conversations"
    assert captured["headers"]["apikey"] == "publishable-test"
    assert captured["headers"]["Authorization"] == "Bearer user-access-jwt"
    assert captured["params"]["owner_user_id"] == f"eq.{OWNER_ID}"
    assert "service_role" not in captured["headers"]["apikey"]

