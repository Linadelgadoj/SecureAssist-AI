from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.domain.errors import StorageError, StorageUnavailable


class ConversationStoreError(StorageError):
    pass


class ConversationStoreUnavailable(ConversationStoreError, StorageUnavailable):
    pass


class SupabaseConversationRepository:
    """Use PostgREST with the caller's JWT so Supabase RLS stays in force."""

    def __init__(self, settings: Settings, access_token: str):
        self.settings = settings
        self.access_token = access_token

    async def list_conversations(self, owner_user_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self._request("GET", "conversations", params={
            "select": "id,title,state,created_at,last_activity_at",
            "owner_user_id": f"eq.{owner_user_id}",
            "order": "last_activity_at.desc,id.desc",
            "limit": str(limit),
            "offset": str(offset),
        })

    async def create_conversation(self, owner_user_id: str, title: str) -> dict[str, Any]:
        rows = await self._request("POST", "conversations", json={
            "owner_user_id": owner_user_id, "title": title,
        }, prefer="return=representation")
        if not rows:
            raise ConversationStoreError("Conversation insert returned no row")
        return rows[0]

    async def get_conversation(self, owner_user_id: str, conversation_id: str) -> dict[str, Any] | None:
        rows = await self._request("GET", "conversations", params={
            "select": "id,title,state,created_at,last_activity_at",
            "owner_user_id": f"eq.{owner_user_id}",
            "id": f"eq.{conversation_id}",
            "limit": "1",
        })
        return rows[0] if rows else None

    async def list_messages(self, owner_user_id: str, conversation_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self._request("GET", "messages", params={
            "select": "id,conversation_id,role,content_text,processing_state,created_at",
            "owner_user_id": f"eq.{owner_user_id}",
            "conversation_id": f"eq.{conversation_id}",
            "order": "created_at.asc,id.asc",
            "limit": str(limit),
            "offset": str(offset),
        })

    async def create_message(self, owner_user_id: str, conversation_id: str, content_text: str) -> dict[str, Any]:
        rows = await self._request("POST", "messages", json={
            "owner_user_id": owner_user_id,
            "conversation_id": conversation_id,
            "role": "installer",
            "content_text": content_text,
        }, prefer="return=representation")
        if not rows:
            raise ConversationStoreError("Message insert returned no row")
        return rows[0]

    async def _request(self, method: str, table: str, *, params: dict[str, str] | None = None,
                       json: dict[str, Any] | None = None, prefer: str | None = None) -> list[dict[str, Any]]:
        if not self.settings.supabase_url or not self.settings.supabase_publishable_key or not self.access_token:
            raise ConversationStoreUnavailable("Supabase Postgres is not configured")

        headers = {
            "apikey": self.settings.supabase_publishable_key,
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        if json is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=4.0)) as client:
                response = await client.request(
                    method,
                    f"{self.settings.supabase_url.rstrip('/')}/rest/v1/{table}",
                    params=params,
                    json=json,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise ConversationStoreUnavailable() from exc

        if response.status_code >= 500:
            raise ConversationStoreUnavailable()
        if response.status_code >= 400:
            raise ConversationStoreError()
        try:
            rows = response.json()
        except ValueError as exc:
            raise ConversationStoreUnavailable() from exc
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ConversationStoreUnavailable()
        return rows
