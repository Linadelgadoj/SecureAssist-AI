"""Usuarios de la aplicación y sus roles."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    # Gestiona catálogo, existencias, ubicaciones y usuarios.
    ADMIN = "admin"
    # Consulta disponibilidad e historial; registra clientes, equipos y reparaciones.
    TECHNICIAN = "technician"


@dataclass(frozen=True)
class AppUser:
    id: str
    email: str
    full_name: str | None
    role: Role
    is_active: bool

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMIN
