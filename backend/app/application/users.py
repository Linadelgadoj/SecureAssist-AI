"""Casos de uso de usuarios: alta automática al iniciar sesión y gestión de roles."""
from __future__ import annotations

from collections.abc import Collection

from app.domain.errors import ForbiddenError, NotFoundError
from app.domain.ports import UserRepository
from app.domain.users import AppUser, Role


def require_admin(actor: AppUser) -> None:
    if not actor.is_admin:
        raise ForbiddenError("Only administrators can perform this action")


class UserService:
    def __init__(self, repository: UserRepository, admin_emails: Collection[str] = ()):
        self._repository = repository
        self._admin_emails = {email.lower() for email in admin_emails}

    async def resolve(self, claims: dict) -> AppUser:
        """Convierte las claims del token en el usuario de la aplicación.

        La primera vez lo registra como técnico; los correos de ADMIN_EMAILS
        siempre quedan como administradores. Un usuario desactivado no entra.
        """
        email = claims.get("email")
        if not isinstance(email, str) or not email:
            raise ForbiddenError("The identity has no email")
        metadata = claims.get("user_metadata") if isinstance(claims.get("user_metadata"), dict) else {}
        full_name = metadata.get("full_name") or metadata.get("name") or claims.get("name")
        user = await self._repository.sign_in(
            str(claims["sub"]), email.lower(),
            full_name if isinstance(full_name, str) else None,
            force_admin=email.lower() in self._admin_emails,
        )
        if not user.is_active:
            raise ForbiddenError("User is deactivated")
        return user

    async def list_users(self, actor: AppUser) -> list[AppUser]:
        require_admin(actor)
        return await self._repository.list_all()

    async def update_user(self, actor: AppUser, user_id: str, *, role: Role | None, is_active: bool | None) -> AppUser:
        require_admin(actor)
        updated = await self._repository.update(user_id, role, is_active)
        if updated is None:
            raise NotFoundError("User not found")
        return updated
