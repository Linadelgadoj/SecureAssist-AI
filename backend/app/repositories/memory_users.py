"""Usuarios en memoria: para DEV_LOGIN sin base de datos, el modo Supabase y las pruebas."""
from __future__ import annotations

from dataclasses import replace

from app.domain.errors import ConflictError
from app.domain.users import AppUser, Role


class InMemoryUserRepository:
    def __init__(self):
        self._users: dict[str, AppUser] = {}

    async def sign_in(self, user_id: str, email: str, full_name: str | None, force_admin: bool) -> AppUser:
        if any(u.email == email and u.id != user_id for u in self._users.values()):
            raise ConflictError("Este correo ya está asociado a otro usuario.", "EMAIL_IN_USE")
        current = self._users.get(user_id)
        if current is None:
            user = AppUser(user_id, email, full_name, Role.ADMIN if force_admin else Role.TECHNICIAN, True)
        else:
            user = replace(current, email=email, full_name=full_name or current.full_name,
                           role=Role.ADMIN if force_admin else current.role)
        self._users[user_id] = user
        return user

    async def get(self, user_id: str) -> AppUser | None:
        return self._users.get(user_id)

    async def list_all(self) -> list[AppUser]:
        return sorted(self._users.values(), key=lambda u: u.email.lower())

    async def update(self, user_id: str, role: Role | None, is_active: bool | None) -> AppUser | None:
        current = self._users.get(user_id)
        if current is None:
            return None
        updated = replace(current, role=role or current.role,
                          is_active=current.is_active if is_active is None else is_active)
        active_admins = [u for u in self._users.values() if u.is_admin and u.is_active]
        if current in active_admins and not (updated.is_admin and updated.is_active) and len(active_admins) == 1:
            raise ConflictError("Debe quedar al menos un administrador activo.", "LAST_ADMIN")
        self._users[user_id] = updated
        return updated
