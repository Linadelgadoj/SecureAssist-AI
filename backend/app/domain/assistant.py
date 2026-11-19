"""Tipos del asistente conversacional, independientes del proveedor de IA."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.domain.errors import DomainError


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatTurn:
    """Un turno enviado al modelo. `tool_name` solo aplica a role="tool"."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_name: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    """Herramienta que el modelo puede pedir. `parameters` es JSON Schema."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ModelReply:
    content: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)


class AssistantUnavailable(DomainError):
    """El proveedor de IA no respondió (apagado, sin modelo, tiempo agotado)."""

    def __init__(self, message: str = "El asistente no está disponible en este momento. Intenta de nuevo."):
        super().__init__(message)
        self.message = message
