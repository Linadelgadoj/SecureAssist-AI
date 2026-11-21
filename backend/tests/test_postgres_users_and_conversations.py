"""Roles y conversaciones sobre PostgreSQL real."""
import asyncio

import asyncpg
import pytest

from postgres_support import TEST_DATABASE_URL, login, pg_client, requires_postgres  # noqa: F401

pytestmark = requires_postgres


def sql(query: str, *args):
    async def _run():
        conn = await asyncpg.connect(TEST_DATABASE_URL)
        try:
            return await conn.execute(query, *args)
        finally:
            await conn.close()

    return asyncio.run(_run())


def test_roles_are_assigned_on_first_sign_in(pg_client):
    admin = pg_client.get("/api/v1/me", headers=login(pg_client)).json()
    technician = pg_client.get("/api/v1/me", headers=login(pg_client, "tecnico@localhost")).json()
    assert (admin["email"], admin["role"]) == ("dev@localhost", "admin")
    assert (technician["email"], technician["role"]) == ("tecnico@localhost", "technician")


def test_only_admins_manage_users(pg_client):
    admin = login(pg_client)
    pg_client.get("/api/v1/me", headers=admin)
    technician = login(pg_client, "tecnico@localhost")
    tech_id = pg_client.get("/api/v1/me", headers=technician).json()["id"]

    denied = pg_client.get("/api/v1/users", headers=technician)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN"

    users = pg_client.get("/api/v1/users", headers=admin).json()
    assert {u["email"] for u in users} == {"dev@localhost", "tecnico@localhost"}

    promoted = pg_client.patch(f"/api/v1/users/{tech_id}", json={"role": "admin"}, headers=admin)
    assert promoted.status_code == 200 and promoted.json()["role"] == "admin"


def test_last_active_admin_cannot_be_demoted_or_deactivated(pg_client):
    admin = login(pg_client)
    admin_id = pg_client.get("/api/v1/me", headers=admin).json()["id"]
    for change in ({"role": "technician"}, {"is_active": False}):
        response = pg_client.patch(f"/api/v1/users/{admin_id}", json=change, headers=admin)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "LAST_ADMIN"
    assert pg_client.get("/api/v1/me", headers=admin).json()["role"] == "admin"


def test_deactivated_user_is_refused(pg_client):
    admin = login(pg_client)
    pg_client.get("/api/v1/me", headers=admin)
    technician = login(pg_client, "tecnico@localhost")
    tech_id = pg_client.get("/api/v1/me", headers=technician).json()["id"]
    assert pg_client.patch(f"/api/v1/users/{tech_id}", json={"is_active": False}, headers=admin).status_code == 200
    assert pg_client.get("/api/v1/conversations", headers=technician).status_code == 403


def test_conversations_persist_and_are_private(pg_client):
    admin = login(pg_client)
    technician = login(pg_client, "tecnico@localhost")
    conversation = pg_client.post("/api/v1/conversations", json={"title": "DVR sin video"}, headers=technician).json()
    sent = pg_client.post(f"/api/v1/conversations/{conversation['id']}/messages",
                          json={"content_text": "El canal 3 está en negro"}, headers=technician)
    assert sent.status_code == 201

    page = pg_client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=technician).json()
    assert [m["content_text"] for m in page["items"]] == ["El canal 3 está en negro"]
    # Ni siquiera un administrador ve conversaciones privadas de otro usuario.
    assert pg_client.get(f"/api/v1/conversations/{conversation['id']}", headers=admin).status_code == 404
    assert pg_client.get("/api/v1/conversations", headers=admin).json()["items"] == []


def test_database_rejects_negative_stock_and_inconsistent_movements(pg_client):
    login(pg_client)
    pg_client.get("/api/v1/me", headers=login(pg_client))
    sql("INSERT INTO products (id, sku, name, category) VALUES "
        "('11111111-1111-4111-8111-111111111111', 'FU-12V', 'Fuente 12V 2A', 'fuente')")
    sql("INSERT INTO stock_locations (id, name) VALUES ('22222222-2222-4222-8222-222222222222', 'Bodega')")
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        sql("INSERT INTO stock_levels (product_id, location_id, quantity) VALUES "
            "('11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', -1)")
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        # Una salida por reparación debe ir enlazada a una reparación.
        sql("INSERT INTO stock_movements (product_id, location_id, quantity_delta, reason, created_by) VALUES "
            "('11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', -1, 'repair', "
            "'00000000-0000-4000-8000-000000000001')")
