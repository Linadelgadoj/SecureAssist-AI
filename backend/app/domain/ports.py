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


# ---------------------------------------------------------------------------
# Inventario. Tres puertos pequeños en lugar de uno grande (segregación de
# interfaces): catálogo y existencias, clientes y equipos, reparaciones.
# Los datos de entrada son dicts ya validados por los esquemas de la API.
# ---------------------------------------------------------------------------


class CatalogRepository(Protocol):
    async def list_products(self, *, query: str | None, category: str | None,
                            include_inactive: bool, low_stock_only: bool) -> list[Row]: ...

    async def get_product(self, product_id: str) -> Row | None: ...

    async def create_product(self, data: Row) -> Row: ...

    async def update_product(self, product_id: str, data: Row) -> Row | None: ...

    async def list_locations(self, include_inactive: bool) -> list[Row]: ...

    async def create_location(self, data: Row) -> Row: ...

    async def update_location(self, location_id: str, data: Row) -> Row | None: ...

    async def record_movement(self, *, product_id: str, location_id: str, delta: int, reason: str,
                              actor_id: str, note: str | None) -> Row:
        """Registra el movimiento y actualiza la existencia en una sola transacción.
        ConflictError("INSUFFICIENT_STOCK") si la existencia quedaría negativa."""
        ...

    async def adjust_to(self, *, product_id: str, location_id: str, counted: int,
                        actor_id: str, note: str | None) -> Row: ...

    async def transfer(self, *, product_id: str, from_location_id: str, to_location_id: str,
                       quantity: int, actor_id: str, note: str | None) -> list[Row]: ...

    async def list_movements(self, *, product_id: str | None, limit: int) -> list[Row]: ...


class ClientRepository(Protocol):
    async def list_clients(self, *, query: str | None, limit: int, offset: int) -> list[Row]: ...

    async def get_client(self, client_id: str) -> Row | None:
        """Cliente con sus equipos instalados."""
        ...

    async def create_client(self, data: Row, actor_id: str) -> Row: ...

    async def update_client(self, client_id: str, data: Row) -> Row | None: ...

    async def create_equipment(self, client_id: str, data: Row, actor_id: str) -> Row: ...

    async def update_equipment(self, equipment_id: str, data: Row) -> Row | None: ...

    async def get_equipment(self, equipment_id: str) -> Row | None:
        """Equipo con su historial de reparaciones."""
        ...


class RepairRepository(Protocol):
    async def list_repairs(self, *, status: str | None, client_id: str | None, equipment_id: str | None,
                           technician_id: str | None, limit: int, offset: int) -> list[Row]: ...

    async def get_repair(self, repair_id: str) -> Row | None:
        """Reparación con los repuestos usados."""
        ...

    async def create_repair(self, data: Row, technician_id: str) -> Row:
        """Valida que el equipo sea del cliente y la conversación del técnico;
        marca el equipo como en reparación."""
        ...

    async def update_repair(self, repair_id: str, data: Row) -> Row:
        """ConflictError("REPAIR_CLOSED") si ya estaba cerrada."""
        ...

    async def add_part(self, *, repair_id: str, product_id: str, location_id: str,
                       quantity: int, actor_id: str, note: str | None) -> Row:
        """Descuenta el repuesto del stock enlazado a la reparación."""
        ...
