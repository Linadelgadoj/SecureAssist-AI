"""Utilidades para pruebas contra PostgreSQL real (base secureassist_test).

Las pruebas que las usan se omiten si TEST_DATABASE_URL no está definido, para que
la suite siga funcionando en equipos sin Docker.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()
ORIGIN = "http://localhost:5173"

requires_postgres = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL no está definido")


def reset_database() -> None:
    async def _reset():
        conn = await asyncpg.connect(TEST_DATABASE_URL)
        try:
            await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        finally:
            await conn.close()

    asyncio.run(_reset())


def make_settings(**overrides) -> Settings:
    values = dict(
        app_env="development", cors_origins=[ORIGIN], frontend_origin=ORIGIN,
        supabase_url="", supabase_publishable_key="",
        supabase_auth_callback_url="http://testserver/api/v1/auth/google/callback",
        frontend_auth_success_url=f"{ORIGIN}/", auth_cookie_secure=False,
        auth_cookie_name="secureassist_refresh", auth_cookie_domain=None,
        auth_cookie_max_age_seconds=None, dev_login=True,
        database_url=TEST_DATABASE_URL, admin_emails=frozenset({"dev@localhost"}),
    )
    values.update(overrides)
    return Settings(**values)


def login(client: TestClient, email: str = "dev@localhost") -> dict[str, str]:
    """Inicia sesión con el login de prueba y devuelve la cabecera Authorization."""
    client.cookies.clear()
    start = client.get("/api/v1/auth/google/start", params={"login_hint": email}, follow_redirects=False)
    client.get(start.headers["location"], follow_redirects=False)
    token = client.get("/api/v1/auth/session", headers={"Origin": ORIGIN}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pg_client():
    """Cliente con la app sobre una base vacía y migrada (el lifespan migra al iniciar)."""
    reset_database()
    with TestClient(create_app(make_settings())) as client:
        yield client
