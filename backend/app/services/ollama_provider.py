"""Adaptador de Ollama (modelo local) para el puerto LanguageModel.

Usa /api/chat sin streaming y con `think: false`: los modelos con razonamiento
(qwen3.5) responden bastante más rápido y el razonamiento no se muestra al usuario.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.domain.assistant import AssistantUnavailable, ChatTurn, ModelReply, ToolCall, ToolSpec


def _turn_payload(turn: ChatTurn) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": turn.role, "content": turn.content}
    if turn.tool_calls:
        payload["tool_calls"] = [{"function": {"name": c.name, "arguments": c.arguments}} for c in turn.tool_calls]
    if turn.tool_name:
        payload["tool_name"] = turn.tool_name
    return payload


def _tool_payload(tool: ToolSpec) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": tool.name, "description": tool.description, "parameters": tool.parameters,
    }}


class OllamaLanguageModel:
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 180.0,
                 client: httpx.AsyncClient | None = None):
        self._url = f"{base_url.rstrip('/')}/api/chat"
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=5.0))

    async def chat(self, turns: list[ChatTurn], tools: list[ToolSpec]) -> ModelReply:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [_turn_payload(turn) for turn in turns],
            "stream": False,
            "think": False,
            # Respuestas técnicas: poca creatividad, más consistencia.
            "options": {"temperature": 0.3},
        }
        if tools:
            body["tools"] = [_tool_payload(tool) for tool in tools]
        try:
            response = await self._client.post(self._url, json=body)
        except httpx.TimeoutException as exc:
            raise AssistantUnavailable("El asistente tardó demasiado en responder. Intenta de nuevo.") from exc
        except httpx.HTTPError as exc:
            raise AssistantUnavailable("No se pudo conectar con el modelo local (Ollama). ¿Está iniciado?") from exc
        if response.status_code == 404:
            raise AssistantUnavailable(f"El modelo «{self._model}» no está instalado en Ollama.")
        if response.status_code >= 400:
            raise AssistantUnavailable()
        try:
            message = response.json().get("message") or {}
        except ValueError as exc:
            raise AssistantUnavailable() from exc
        calls = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function") or {}
            arguments = function.get("arguments")
            if isinstance(function.get("name"), str) and isinstance(arguments, dict):
                calls.append(ToolCall(function["name"], arguments))
        content = message.get("content")
        return ModelReply(content=content.strip() if isinstance(content, str) else "", tool_calls=tuple(calls))

    async def aclose(self) -> None:
        await self._client.aclose()
