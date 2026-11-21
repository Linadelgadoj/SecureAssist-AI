"""Historial de conversaciones en PostgreSQL local.

Sin RLS de Supabase, el aislamiento lo garantiza el filtro por owner_user_id en
cada consulta, más la clave foránea compuesta (conversación, propietario) de messages.
"""
from __future__ import annotations

from app.db.database import Database
from app.domain.ports import Row

_CONVERSATION_COLUMNS = "id, title, state, created_at, last_activity_at"
_MESSAGE_COLUMNS = "id, conversation_id, role, content_text, processing_state, created_at"


class PostgresConversationRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_conversations(self, owner_user_id: str, limit: int, offset: int) -> list[Row]:
        async with self._db.connection() as conn:
            rows = await conn.fetch(
                f"SELECT {_CONVERSATION_COLUMNS} FROM conversations WHERE owner_user_id = $1"
                " ORDER BY last_activity_at DESC, id DESC LIMIT $2 OFFSET $3",
                owner_user_id, limit, offset,
            )
        return [dict(row) for row in rows]

    async def create_conversation(self, owner_user_id: str, title: str) -> Row:
        async with self._db.connection() as conn:
            row = await conn.fetchrow(
                f"INSERT INTO conversations (owner_user_id, title) VALUES ($1, $2) RETURNING {_CONVERSATION_COLUMNS}",
                owner_user_id, title,
            )
        return dict(row)

    async def get_conversation(self, owner_user_id: str, conversation_id: str) -> Row | None:
        async with self._db.connection() as conn:
            row = await conn.fetchrow(
                f"SELECT {_CONVERSATION_COLUMNS} FROM conversations WHERE owner_user_id = $1 AND id = $2",
                owner_user_id, conversation_id,
            )
        return dict(row) if row else None

    async def list_messages(self, owner_user_id: str, conversation_id: str, limit: int, offset: int) -> list[Row]:
        async with self._db.connection() as conn:
            rows = await conn.fetch(
                f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE owner_user_id = $1 AND conversation_id = $2"
                " ORDER BY created_at, id LIMIT $3 OFFSET $4",
                owner_user_id, conversation_id, limit, offset,
            )
        return [dict(row) for row in rows]

    async def create_message(self, owner_user_id: str, conversation_id: str, content_text: str) -> Row:
        return await self._insert_message(owner_user_id, conversation_id, content_text, "installer", "received")

    async def create_assistant_message(self, owner_user_id: str, conversation_id: str, content_text: str) -> Row:
        return await self._insert_message(owner_user_id, conversation_id, content_text, "assistant", "completed")

    async def _insert_message(self, owner_user_id: str, conversation_id: str, content_text: str,
                              role: str, processing_state: str) -> Row:
        async with self._db.transaction() as conn:
            row = await conn.fetchrow(
                "INSERT INTO messages (owner_user_id, conversation_id, role, content_text, processing_state)"
                f" VALUES ($1, $2, $3, $4, $5) RETURNING {_MESSAGE_COLUMNS}",
                owner_user_id, conversation_id, role, content_text, processing_state,
            )
            await conn.execute(
                "UPDATE conversations SET last_activity_at = $3 WHERE id = $1 AND owner_user_id = $2",
                conversation_id, owner_user_id, row["created_at"],
            )
        return dict(row)
