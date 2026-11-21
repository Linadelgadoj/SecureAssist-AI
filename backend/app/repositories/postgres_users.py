"""Usuarios y roles en PostgreSQL local."""
from __future__ import annotations

import asyncpg

from app.db.database import Database
from app.domain.errors import ConflictError
from app.domain.users import AppUser, Role

_COLUMNS = "id, email, full_name, role, is_active"


def _to_user(row: asyncpg.Record) -> AppUser:
    return AppUser(id=str(row["id"]), email=row["email"], full_name=row["full_name"],
                   role=Role(row["role"]), is_active=row["is_active"])


class PostgresUserRepository:
    def __init__(self, database: Database):
        self._db = database

    async def sign_in(self, user_id: str, email: str, full_name: str | None, force_admin: bool) -> AppUser:
        async with self._db.connection() as conn:
            try:
                row = await conn.fetchrow(
                    f"""
                    INSERT INTO app_users (id, email, full_name, role)
                    VALUES ($1, $2, $3, CASE WHEN $4 THEN 'admin' ELSE 'technician' END)
                    ON CONFLICT (id) DO UPDATE SET
                        email = EXCLUDED.email,
                        full_name = coalesce(EXCLUDED.full_name, app_users.full_name),
                        role = CASE WHEN $4 THEN 'admin' ELSE app_users.role END,
                        updated_at = now()
                    RETURNING {_COLUMNS}
                    """,
                    user_id, email, full_name, force_admin,
                )
            except asyncpg.exceptions.UniqueViolationError as exc:
                # Otro id ya usa este correo (p. ej. se recreó la cuenta en el proveedor).
                raise ConflictError("Este correo ya está asociado a otro usuario.", "EMAIL_IN_USE") from exc
        return _to_user(row)

    async def get(self, user_id: str) -> AppUser | None:
        async with self._db.connection() as conn:
            row = await conn.fetchrow(f"SELECT {_COLUMNS} FROM app_users WHERE id = $1", user_id)
        return _to_user(row) if row else None

    async def list_all(self) -> list[AppUser]:
        async with self._db.connection() as conn:
            rows = await conn.fetch(f"SELECT {_COLUMNS} FROM app_users ORDER BY lower(email)")
        return [_to_user(row) for row in rows]

    async def update(self, user_id: str, role: Role | None, is_active: bool | None) -> AppUser | None:
        async with self._db.transaction() as conn:
            # Bloquea a los administradores activos para que dos cambios simultáneos
            # no puedan dejar la aplicación sin ninguno.
            admins = {str(r["id"]) for r in await conn.fetch(
                "SELECT id FROM app_users WHERE role = 'admin' AND is_active FOR UPDATE")}
            row = await conn.fetchrow(
                f"""
                UPDATE app_users SET
                    role = coalesce($2, role),
                    is_active = coalesce($3, is_active),
                    updated_at = now()
                WHERE id = $1
                RETURNING {_COLUMNS}
                """,
                user_id, role.value if role else None, is_active,
            )
            if row is None:
                return None
            user = _to_user(row)
            still_admin = user.is_admin and user.is_active
            if user_id in admins and not still_admin and len(admins) == 1:
                raise ConflictError("Debe quedar al menos un administrador activo.", "LAST_ADMIN")
        return user
