"""Casos de uso del historial de conversaciones.

Aquí viven las reglas de negocio (propiedad de la conversación, título por defecto);
las rutas solo traducen HTTP y el repositorio solo persiste.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.errors import NotFoundError
from app.domain.ports import ConversationRepository, Row

DEFAULT_TITLE = "Nueva conversación"


@dataclass(frozen=True)
class Page:
    """Una página de resultados y si existe al menos un elemento más."""

    items: list[Row]
    has_more: bool


class ConversationService:
    def __init__(self, repository: ConversationRepository):
        self._repository = repository

    async def start_conversation(self, owner_id: str, title: str | None) -> Row:
        return await self._repository.create_conversation(owner_id, title or DEFAULT_TITLE)

    async def list_conversations(self, owner_id: str, limit: int, offset: int) -> Page:
        rows = await self._repository.list_conversations(owner_id, limit + 1, offset)
        return Page(rows[:limit], len(rows) > limit)

    async def get_conversation(self, owner_id: str, conversation_id: str) -> Row:
        conversation = await self._repository.get_conversation(owner_id, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found")
        return conversation

    async def list_messages(self, owner_id: str, conversation_id: str, limit: int, offset: int) -> Page:
        await self.get_conversation(owner_id, conversation_id)
        rows = await self._repository.list_messages(owner_id, conversation_id, limit + 1, offset)
        return Page(rows[:limit], len(rows) > limit)

    async def send_message(self, owner_id: str, conversation_id: str, content_text: str) -> Row:
        await self.get_conversation(owner_id, conversation_id)
        return await self._repository.create_message(owner_id, conversation_id, content_text)
