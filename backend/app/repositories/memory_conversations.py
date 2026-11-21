"""Almacenamiento de conversaciones en memoria, SOLO para el login de prueba local.

Replica la interfaz de SupabaseConversationRepository filtrando siempre por
owner_user_id. Los datos se pierden al reiniciar el backend.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_CONVERSATION_FIELDS = ("id", "title", "state", "created_at", "last_activity_at")
_MESSAGE_FIELDS = ("id", "conversation_id", "role", "content_text", "processing_state", "created_at")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: row[field] for field in fields}


class InMemoryConversationRepository:
    def __init__(self):
        self.conversations: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []

    async def list_conversations(self, owner_user_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        rows = sorted(
            (c for c in self.conversations if c["owner_user_id"] == owner_user_id),
            key=lambda c: (c["last_activity_at"], c["id"]),
            reverse=True,
        )
        return [_pick(c, _CONVERSATION_FIELDS) for c in rows[offset:offset + limit]]

    async def create_conversation(self, owner_user_id: str, title: str) -> dict[str, Any]:
        now = _now()
        row = {"id": str(uuid4()), "owner_user_id": owner_user_id, "title": title, "state": "open",
               "created_at": now, "last_activity_at": now}
        self.conversations.append(row)
        return _pick(row, _CONVERSATION_FIELDS)

    async def get_conversation(self, owner_user_id: str, conversation_id: str) -> dict[str, Any] | None:
        row = self._find(owner_user_id, conversation_id)
        return _pick(row, _CONVERSATION_FIELDS) if row else None

    async def list_messages(self, owner_user_id: str, conversation_id: str, limit: int, offset: int) -> list[dict[str, Any]]:
        rows = [m for m in self.messages
                if m["owner_user_id"] == owner_user_id and m["conversation_id"] == conversation_id]
        return [_pick(m, _MESSAGE_FIELDS) for m in rows[offset:offset + limit]]

    async def create_message(self, owner_user_id: str, conversation_id: str, content_text: str) -> dict[str, Any]:
        return self._insert(owner_user_id, conversation_id, content_text, "installer", "received")

    async def create_assistant_message(self, owner_user_id: str, conversation_id: str, content_text: str) -> dict[str, Any]:
        return self._insert(owner_user_id, conversation_id, content_text, "assistant", "completed")

    def _insert(self, owner_user_id: str, conversation_id: str, content_text: str,
                role: str, processing_state: str) -> dict[str, Any]:
        now = _now()
        row = {"id": str(uuid4()), "conversation_id": conversation_id, "owner_user_id": owner_user_id,
               "role": role, "content_text": content_text, "processing_state": processing_state, "created_at": now}
        self.messages.append(row)
        conversation = self._find(owner_user_id, conversation_id)
        if conversation:
            conversation["last_activity_at"] = now
        return _pick(row, _MESSAGE_FIELDS)

    def _find(self, owner_user_id: str, conversation_id: str) -> dict[str, Any] | None:
        return next((c for c in self.conversations
                     if c["id"] == conversation_id and c["owner_user_id"] == owner_user_id), None)
