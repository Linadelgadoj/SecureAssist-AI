"""Aplica las migraciones de PostgreSQL.

Uso, desde la carpeta backend con el entorno activado (lee el .env de la raíz):
    python -m app.db.migrate
No suele hacer falta: el backend también migra al arrancar.
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

from app.db.database import Database


async def _main() -> int:
    load_dotenv()
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("DATABASE_URL no está definido.", file=sys.stderr)
        return 1
    database = Database(url, max_size=1)
    await database.connect()
    try:
        applied = await database.migrate()
    finally:
        await database.close()
    print("Migraciones aplicadas: " + (", ".join(applied) if applied else "ninguna (al día)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
