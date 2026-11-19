"""Caso de uso: generar la respuesta del asistente para una conversación.

Flujo: historial reciente -> modelo -> (herramientas de solo lectura)* -> respuesta
guardada como mensaje 'assistant'. El modelo y las herramientas llegan por
inyección, así que se prueba con un modelo falso y se cambia de proveedor sin
tocar este archivo.
"""
from __future__ import annotations

from app.application.assistant_prompt import SYSTEM_PROMPT
from app.application.assistant_tools import AssistantTools
from app.domain.assistant import AssistantUnavailable, ChatTurn
from app.domain.errors import ConflictError, NotFoundError
from app.domain.ports import ConversationRepository, LanguageModel, Row

HISTORY_MESSAGES = 20          # turnos recientes que se envían al modelo
HISTORY_CHARS = 4000           # recorte por mensaje (el modelo local tiene contexto limitado)
MAX_TOOL_ROUNDS = 3            # rondas de herramientas antes de exigir una respuesta
MAX_CALLS_PER_ROUND = 3
MAX_REPLY_CHARS = 8000         # límite de la columna content_text


class AssistantService:
    def __init__(self, conversations: ConversationRepository, model: LanguageModel, tools: AssistantTools):
        self._conversations = conversations
        self._model = model
        self._tools = tools

    async def reply(self, owner_id: str, conversation_id: str) -> Row:
        if await self._conversations.get_conversation(owner_id, conversation_id) is None:
            raise NotFoundError("Conversation not found")
        history = await self._conversations.list_messages(owner_id, conversation_id, 1000, 0)
        if not history or history[-1]["role"] != "installer":
            raise ConflictError("No hay un mensaje nuevo del técnico para responder.", "NOTHING_TO_REPLY")

        turns = [ChatTurn("system", SYSTEM_PROMPT)] + [
            ChatTurn("user" if message["role"] == "installer" else "assistant",
                     message["content_text"][:HISTORY_CHARS])
            for message in history[-HISTORY_MESSAGES:]
        ]
        answer = await self._run(turns)
        return await self._conversations.create_assistant_message(owner_id, conversation_id, answer[:MAX_REPLY_CHARS])

    async def _run(self, turns: list[ChatTurn]) -> str:
        tools = self._tools.specs
        for _ in range(MAX_TOOL_ROUNDS):
            reply = await self._model.chat(turns, tools)
            if not reply.tool_calls:
                if reply.content:
                    return reply.content
                break
            calls = reply.tool_calls[:MAX_CALLS_PER_ROUND]
            turns.append(ChatTurn("assistant", reply.content, tool_calls=calls))
            for call in calls:
                turns.append(ChatTurn("tool", await self._tools.run(call.name, call.arguments), tool_name=call.name))
        # Se agotaron las rondas (o vino vacío): se pide la respuesta final sin herramientas.
        final = await self._model.chat(turns, [])
        if not final.content:
            raise AssistantUnavailable("El asistente no generó una respuesta. Intenta reformular el mensaje.")
        return final.content
