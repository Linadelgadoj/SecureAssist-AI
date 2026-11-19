"""Inventario sobre PostgreSQL real: permisos, existencias y ciclo de una reparación."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.db.database import Database
from app.domain.errors import ConflictError
from app.main import create_app
from app.repositories.postgres_inventory import PostgresRepairRepository
from postgres_support import TEST_DATABASE_URL, login, make_settings, pg_client, requires_postgres  # noqa: F401

pytestmark = requires_postgres
API = "/api/v1"


@pytest.fixture
def actors(pg_client):
    admin = login(pg_client)
    technician = login(pg_client, "tecnico@localhost")
    # Registra a ambos usuarios (alta automática al primer acceso).
    pg_client.get(f"{API}/me", headers=admin)
    pg_client.get(f"{API}/me", headers=technician)
    return pg_client, admin, technician


def make_catalog(client, admin):
    product = client.post(f"{API}/products", headers=admin, json={
        "sku": "FU-12V-2A", "name": "Fuente 12V 2A", "category": "fuente", "brand": "Genérica", "min_stock": 3,
    }).json()
    bodega = client.post(f"{API}/locations", headers=admin, json={"name": "Bodega principal"}).json()
    van = client.post(f"{API}/locations", headers=admin, json={"name": "Camioneta 1", "kind": "vehicle"}).json()
    client.post(f"{API}/stock/movements", headers=admin, json={
        "product_id": product["id"], "location_id": bodega["id"], "reason": "receipt", "quantity": 10,
    })
    return product, bodega, van


def stock_of(client, headers, product_id):
    product = client.get(f"{API}/products/{product_id}", headers=headers).json()
    return product["total_quantity"], {s["location_name"]: s["quantity"] for s in product["stock"]}


def test_only_admins_manage_catalog_and_stock(actors):
    client, admin, technician = actors
    product, bodega, _ = make_catalog(client, admin)
    assert client.post(f"{API}/products", headers=technician,
                       json={"sku": "X", "name": "X", "category": "otro"}).status_code == 403
    assert client.post(f"{API}/locations", headers=technician, json={"name": "Mía"}).status_code == 403
    assert client.post(f"{API}/stock/movements", headers=technician, json={
        "product_id": product["id"], "location_id": bodega["id"], "reason": "receipt", "quantity": 1,
    }).status_code == 403
    # Pero el técnico sí consulta la disponibilidad.
    found = client.get(f"{API}/products", params={"q": "fuente"}, headers=technician).json()
    assert [(p["sku"], p["total_quantity"]) for p in found] == [("FU-12V-2A", 10)]


def test_duplicate_sku_is_a_conflict(actors):
    client, admin, _ = actors
    make_catalog(client, admin)
    response = client.post(f"{API}/products", headers=admin, json={"sku": "FU-12V-2A", "name": "Otra", "category": "x"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "SKU_IN_USE"


def test_issue_adjustment_and_transfer(actors):
    client, admin, technician = actors
    product, bodega, van = make_catalog(client, admin)

    too_much = client.post(f"{API}/stock/movements", headers=admin, json={
        "product_id": product["id"], "location_id": bodega["id"], "reason": "issue", "quantity": 11,
    })
    assert too_much.status_code == 409
    assert too_much.json()["error"]["code"] == "INSUFFICIENT_STOCK"
    assert "hay 10" in too_much.json()["error"]["message"]

    adjusted = client.post(f"{API}/stock/movements", headers=admin, json={
        "product_id": product["id"], "location_id": bodega["id"], "reason": "adjustment", "quantity": 8,
        "note": "Conteo físico",
    }).json()
    assert adjusted["quantity_delta"] == -2

    moved = client.post(f"{API}/stock/transfers", headers=admin, json={
        "product_id": product["id"], "from_location_id": bodega["id"], "to_location_id": van["id"], "quantity": 3,
    })
    assert moved.status_code == 201
    assert stock_of(client, technician, product["id"]) == (8, {"Bodega principal": 5, "Camioneta 1": 3})

    history = client.get(f"{API}/stock/movements", params={"product_id": product["id"]}, headers=technician).json()
    # Los dos movimientos del traslado comparten hora (misma transacción), así que no se compara su orden.
    assert sorted(m["reason"] for m in history[:2]) == ["transfer_in", "transfer_out"]
    assert sorted(m["reason"] for m in history[2:]) == ["adjustment", "receipt"]


def test_low_stock_filter(actors):
    client, admin, technician = actors
    product, bodega, _ = make_catalog(client, admin)
    assert client.get(f"{API}/products", params={"low_stock": True}, headers=technician).json() == []
    client.post(f"{API}/stock/movements", headers=admin, json={
        "product_id": product["id"], "location_id": bodega["id"], "reason": "issue", "quantity": 7,
    })
    low = client.get(f"{API}/products", params={"low_stock": True}, headers=technician).json()
    assert [(p["sku"], p["is_low_stock"]) for p in low] == [("FU-12V-2A", True)]


def test_technician_registers_clients_and_equipment(actors):
    client, _, technician = actors
    customer = client.post(f"{API}/clients", headers=technician,
                           json={"name": "Tienda La Esquina", "phone": "3001234567"}).json()
    camera = client.post(f"{API}/clients/{customer['id']}/equipment", headers=technician, json={
        "equipment_type": "Cámara bala", "brand": "Hikvision", "model": "DS-2CE16D0T", "serial_number": "ABC123",
        "site_description": "Entrada principal",
    })
    assert camera.status_code == 201
    duplicate = client.post(f"{API}/clients/{customer['id']}/equipment", headers=technician, json={
        "equipment_type": "Cámara bala", "brand": "hikvision", "serial_number": "abc123",
    })
    assert duplicate.json()["error"]["code"] == "SERIAL_IN_USE"
    listed = client.get(f"{API}/clients", params={"q": "esquina"}, headers=technician).json()
    assert [(c["name"], c["equipment_count"]) for c in listed] == [("Tienda La Esquina", 1)]


def test_full_repair_cycle_consumes_stock_and_updates_equipment(actors):
    client, admin, technician = actors
    product, bodega, _ = make_catalog(client, admin)
    customer = client.post(f"{API}/clients", headers=technician, json={"name": "Conjunto Los Pinos"}).json()
    dvr = client.post(f"{API}/clients/{customer['id']}/equipment", headers=technician,
                      json={"equipment_type": "DVR", "brand": "Dahua"}).json()

    repair = client.post(f"{API}/repairs", headers=technician, json={
        "client_id": customer["id"], "equipment_id": dvr["id"], "problem_description": "No enciende",
    }).json()
    assert repair["status"] == "open"
    assert client.get(f"{API}/equipment/{dvr['id']}", headers=technician).json()["status"] == "in_repair"

    part = client.post(f"{API}/repairs/{repair['id']}/parts", headers=technician, json={
        "product_id": product["id"], "location_id": bodega["id"], "quantity": 2,
    })
    assert part.status_code == 201 and part.json()["reason"] == "repair"
    assert stock_of(client, technician, product["id"])[0] == 8

    detail = client.get(f"{API}/repairs/{repair['id']}", headers=admin).json()
    assert detail["status"] == "in_progress"
    assert [(p["product_sku"], p["quantity_delta"]) for p in detail["parts"]] == [("FU-12V-2A", -2)]

    closed = client.patch(f"{API}/repairs/{repair['id']}", headers=technician, json={
        "diagnosis": "Fuente quemada", "solution": "Cambio de fuente", "status": "resolved",
    }).json()
    assert closed["status"] == "resolved" and closed["closed_at"] is not None

    equipment = client.get(f"{API}/equipment/{dvr['id']}", headers=technician).json()
    assert equipment["status"] == "operational"
    assert [(r["id"], r["parts_count"]) for r in equipment["repairs"]] == [(repair["id"], 2)]

    after_close = client.post(f"{API}/repairs/{repair['id']}/parts", headers=technician, json={
        "product_id": product["id"], "location_id": bodega["id"], "quantity": 1,
    })
    assert after_close.json()["error"]["code"] == "REPAIR_CLOSED"


def test_repair_rules(actors):
    client, admin, technician = actors
    one = client.post(f"{API}/clients", headers=admin, json={"name": "Cliente uno"}).json()
    two = client.post(f"{API}/clients", headers=admin, json={"name": "Cliente dos"}).json()
    camera = client.post(f"{API}/clients/{two['id']}/equipment", headers=admin,
                         json={"equipment_type": "Cámara"}).json()

    mismatch = client.post(f"{API}/repairs", headers=technician, json={
        "client_id": one["id"], "equipment_id": camera["id"], "problem_description": "x",
    })
    assert mismatch.json()["error"]["code"] == "EQUIPMENT_CLIENT_MISMATCH"

    # Una reparación del administrador no la cambia otro técnico.
    admins_repair = client.post(f"{API}/repairs", headers=admin,
                                json={"client_id": one["id"], "problem_description": "Revisión"}).json()
    assert client.patch(f"{API}/repairs/{admins_repair['id']}", headers=technician,
                        json={"diagnosis": "x"}).status_code == 403

    # No se puede enlazar la conversación privada de otra persona.
    private = client.post(f"{API}/conversations", headers=admin, json={"title": "Privada"}).json()
    linked = client.post(f"{API}/repairs", headers=technician, json={
        "client_id": one["id"], "problem_description": "x", "conversation_id": private["id"],
    })
    assert linked.status_code == 404

    mine = client.get(f"{API}/repairs", params={"mine": True}, headers=technician).json()
    assert mine == []


def test_concurrent_parts_never_drive_stock_negative(actors):
    """Dos técnicos piden las 2 últimas unidades a la vez: solo uno las obtiene."""
    client, admin, technician = actors
    product, bodega, _ = make_catalog(client, admin)
    client.post(f"{API}/stock/movements", headers=admin, json={
        "product_id": product["id"], "location_id": bodega["id"], "reason": "adjustment", "quantity": 2,
    })
    customer = client.post(f"{API}/clients", headers=admin, json={"name": "Concurrente"}).json()
    repairs = [client.post(f"{API}/repairs", headers=admin,
                           json={"client_id": customer["id"], "problem_description": f"Caso {i}"}).json()
               for i in range(2)]
    admin_id = client.get(f"{API}/me", headers=admin).json()["id"]

    async def race():
        database = Database(TEST_DATABASE_URL, max_size=4)
        await database.connect()
        try:
            repo = PostgresRepairRepository(database)
            return await asyncio.gather(*(
                repo.add_part(repair_id=r["id"], product_id=product["id"], location_id=bodega["id"],
                              quantity=2, actor_id=admin_id, note=None)
                for r in repairs), return_exceptions=True)
        finally:
            await database.close()

    results = asyncio.run(race())
    assert sum(isinstance(r, dict) for r in results) == 1
    assert sum(isinstance(r, ConflictError) and r.code == "INSUFFICIENT_STOCK" for r in results) == 1
    assert stock_of(client, admin, product["id"])[0] == 0


def test_inventory_without_database_is_unavailable():
    with TestClient(create_app(make_settings(database_url=""))) as client:
        response = client.get(f"{API}/products", headers=login(client))
    assert response.status_code == 503
