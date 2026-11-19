"""Dependencias inyectables de FastAPI.

Es el único lugar donde las rutas obtienen servicios. La composición concreta
(qué proveedor de identidad y qué repositorio) se decide en `app.main.create_app`
y se guarda en `app.state`, así que las pruebas pueden sustituirla sin tocar rutas.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.conversations import ConversationService
from app.domain.ports import AuthProvider

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_provider(request: Request, *, require_configuration: bool = False) -> AuthProvider:
    """Devuelve el proveedor de identidad, creándolo bajo demanda la primera vez.

    Se crea perezosamente para que la API arranque (y /health responda) aunque
    Supabase aún no esté configurado. Con `require_configuration` falla con 503
    si hay que crearlo y falta configuración (lo usa la validación de tokens).
    """
    state = request.app.state
    if state.auth_service is None:
        from app.services.auth_service import AuthService

        settings = state.settings
        if require_configuration:
            try:
                settings.require_auth_configuration()
            except ValueError as exc:
                raise HTTPException(503, "Authentication is not configured") from exc
        state.auth_service = AuthService(settings)
    return state.auth_service


def get_conversation_service(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ConversationService:
    token = credentials.credentials if credentials else ""
    repository = request.app.state.conversation_repository_factory(token)
    return ConversationService(repository)
