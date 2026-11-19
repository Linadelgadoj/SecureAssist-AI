"""Puertos (interfaces) que la aplicación necesita del exterior.

Los casos de uso dependen de estos protocolos, no de Supabase, PostgreSQL ni de un
proveedor de identidad concreto (principio de inversión de dependencias). Cada
adaptador en `app.repositories` o `app.services` los cumple por tipado estructural.
"""
from __future__ import annotations

from typing import Any, Protocol

from app.domain.users import AppUser, Role
from app.schemas.auth import AuthUser

Row = dict[str, Any]


class ConversationRepository(Protocol):
    """Historial privado de un instalador. Toda operación filtra por propietario."""

    async def list_conversations(self, owner_user_id: str, limit: int, offset: int) -> list[Row]: ...

    async def create_conversation(self, owner_user_id: str, title: str) -> Row: ...

    async def get_conversation(self, owner_user_id: str, conversation_id: str) -> Row | None: ...

    async def list_messages(self, owner_user_id: str, conversation_id: str, limit: int, offset: int) -> list[Row]: ...

    async def create_message(self, owner_user_id: str, conversation_id: str, content_text: str) -> Row: ...


class UserRepository(Protocol):
    async def sign_in(self, user_id: str, email: str, full_name: str | None, force_admin: bool) -> AppUser:
        """Crea el usuario la primera vez (técnico por defecto) y actualiza su correo después."""
        ...

    async def get(self, user_id: str) -> AppUser | None: ...

    async def list_all(self) -> list[AppUser]: ...

    async def update(self, user_id: str, role: Role | None, is_active: bool | None) -> AppUser | None:
        """Aplica el cambio de forma atómica. Debe lanzar ConflictError si dejaría
        la aplicación sin ningún administrador activo."""
        ...


class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict: ...


class AuthProvider(Protocol):
    """Flujo de inicio de sesión. Lo cumplen AuthService (Supabase) y DevAuthService."""

    verifier: TokenVerifier

    def start(self, login_hint: str | None = None) -> tuple[str, str]: ...

    def consume_state(self, provided_state: str, cookie_state: str | None) -> Any: ...

    async def exchange_and_validate(self, code: str, verifier: str) -> tuple[str, str, AuthUser, int]: ...

    async def renew(self, refresh_token: str) -> tuple[str, str, AuthUser, int]: ...

    async def logout(self, refresh_token: str | None) -> None: ...

    async def aclose(self) -> None: ...
