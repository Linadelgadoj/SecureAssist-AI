"""Conexión a PostgreSQL con asyncpg y ejecución de migraciones SQL.

Las migraciones son los archivos `backend/migrations/postgres/NNNN_*.sql`, se aplican
en orden, cada una en su propia transacción, y quedan registradas en
`schema_migrations` para no repetirse.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import asyncpg

from app.domain.errors import StorageError, StorageUnavailable

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "postgres"


class Database:
    def __init__(self, url: str, *, min_size: int = 1, max_size: int = 10):
        self._url = url
        self._min_size = min_size
        self._max_size = max_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self._url, min_size=self._min_size, max_size=self._max_size, command_timeout=10
            )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[asyncpg.Connection]:
        """Conexión del pool; traduce fallos de la base a errores de dominio."""
        if self._pool is None:
            raise StorageUnavailable("Database is not connected")
        try:
            async with self._pool.acquire() as connection:
                yield connection
        except (OSError, asyncpg.exceptions.ConnectionDoesNotExistError,
                asyncpg.exceptions.CannotConnectNowError, asyncpg.exceptions.TooManyConnectionsError) as exc:
            raise StorageUnavailable("Database is unavailable") from exc
        except asyncpg.exceptions.PostgresError as exc:
            # Las violaciones de reglas de negocio se traducen antes, en los repositorios.
            raise StorageError("Database rejected the operation") from exc

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        async with self.connection() as connection:
            async with connection.transaction():
                yield connection

    async def migrate(self, directory: Path = MIGRATIONS_DIR) -> list[str]:
        """Aplica las migraciones pendientes y devuelve sus nombres."""
        applied: list[str] = []
        async with self.connection() as connection:
            await connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            # Un solo proceso migra a la vez aunque arranquen varios.
            await connection.execute("SELECT pg_advisory_lock(727274)")
            try:
                done = {row["name"] for row in await connection.fetch("SELECT name FROM schema_migrations")}
                for path in sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql")):
                    if path.name in done:
                        continue
                    async with connection.transaction():
                        await connection.execute(path.read_text(encoding="utf-8"))
                        await connection.execute("INSERT INTO schema_migrations (name) VALUES ($1)", path.name)
                    applied.append(path.name)
            finally:
                await connection.execute("SELECT pg_advisory_unlock(727274)")
        return applied
