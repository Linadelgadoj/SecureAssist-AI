"""Carga datos de demostración en la base PostgreSQL local (solo desarrollo).

Uso, desde la carpeta backend con el entorno activado (lee el .env de la raíz):
    python -m app.db.seed_demo

Crea los dos usuarios del login de prueba (dev@localhost como administrador y
tecnico@localhost como técnico), ubicaciones, productos con existencias, clientes,
equipos y dos reparaciones. Usa los mismos casos de uso que la API, así que respeta
las reglas de stock. Si ya hay productos, no hace nada.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date

from dotenv import load_dotenv

from app.application.inventory import CatalogService, ClientService, RepairService
from app.db.database import Database
from app.domain.inventory import MovementReason
from app.domain.users import AppUser
from app.repositories.postgres_inventory import (
    PostgresCatalogRepository,
    PostgresClientRepository,
    PostgresRepairRepository,
)
from app.repositories.postgres_users import PostgresUserRepository
from app.services.dev_auth import DEV_TECHNICIAN, DEV_USER

LOCATIONS = [("Bodega principal", "warehouse"), ("Camioneta 1", "vehicle")]
# sku, nombre, categoría, marca, modelo, stock mínimo, en bodega, a la camioneta
PRODUCTS = [
    ("CAM-HK-B2MP", "Cámara bala 2MP", "camara", "Hikvision", "DS-2CE16D0T-IRF", 4, 12, 3),
    ("CAM-DH-D4MP", "Cámara domo 4MP", "camara", "Dahua", "HAC-HDW1400TL", 3, 6, 0),
    ("DVR-HK-8CH", "DVR 8 canales", "dvr_nvr", "Hikvision", "DS-7208HGHI-K1", 1, 2, 0),
    ("FU-12V-2A", "Fuente 12V 2A", "fuente", "Genérica", None, 5, 20, 6),
    ("FU-12V-10A", "Fuente centralizada 12V 10A 9 salidas", "fuente", "Genérica", None, 2, 1, 0),
    ("BAL-HD-PAR", "Balun HD (par)", "conector", "Genérica", None, 10, 40, 10),
    ("CON-BNC-RG", "Conector BNC para RG59", "conector", "Genérica", None, 20, 15, 0),
    ("DD-1TB-PUR", "Disco duro 1TB vigilancia", "disco", "WD Purple", "WD10PURZ", 2, 3, 0),
]


async def seed(database: Database) -> bool:
    users = PostgresUserRepository(database)
    admin: AppUser = await users.sign_in(DEV_USER.id, DEV_USER.email, DEV_USER.name, force_admin=True)
    tech: AppUser = await users.sign_in(DEV_TECHNICIAN.id, DEV_TECHNICIAN.email, DEV_TECHNICIAN.name,
                                        force_admin=False)
    catalog = CatalogService(PostgresCatalogRepository(database))
    clients = ClientService(PostgresClientRepository(database))
    repairs = RepairService(PostgresRepairRepository(database))

    if await catalog.search_products(admin):
        return False

    location = {name: str((await catalog.create_location(admin, {"name": name, "kind": kind}))["id"])
                for name, kind in LOCATIONS}
    product = {}
    for sku, name, category, brand, model, minimum, in_warehouse, to_van in PRODUCTS:
        created = await catalog.create_product(admin, {
            "sku": sku, "name": name, "category": category, "brand": brand, "model": model, "min_stock": minimum,
        })
        product[sku] = str(created["id"])
        await catalog.register_movement(admin, product_id=product[sku], location_id=location["Bodega principal"],
                                        reason=MovementReason.RECEIPT, quantity=in_warehouse,
                                        note="Inventario inicial")
        if to_van:
            await catalog.transfer(admin, product_id=product[sku], from_location_id=location["Bodega principal"],
                                   to_location_id=location["Camioneta 1"], quantity=to_van,
                                   note="Carga de la camioneta")

    store = await clients.create_client(tech, {"name": "Tienda La Esquina", "phone": "3001234567",
                                               "address": "Cra 10 # 5-20, Cali"})
    condo = await clients.create_client(tech, {"name": "Conjunto Residencial Los Pinos",
                                               "document_id": "900123456-1", "phone": "6023334455",
                                               "address": "Calle 13 # 80-15, Cali"})
    dvr = await clients.add_equipment(tech, str(condo["id"]), {
        "equipment_type": "DVR", "brand": "Hikvision", "model": "DS-7208HGHI-K1", "serial_number": "J12345678",
        "site_description": "Portería", "installed_on": date(2025, 3, 14)})
    await clients.add_equipment(tech, str(condo["id"]), {
        "equipment_type": "Cámara bala", "brand": "Hikvision", "serial_number": "K98765432",
        "site_description": "Parqueadero sótano"})
    await clients.add_equipment(tech, str(store["id"]), {
        "equipment_type": "Cámara domo", "brand": "Dahua", "site_description": "Caja registradora"})

    # Una reparación resuelta con repuesto (historial) y otra abierta.
    old = await repairs.open_repair(tech, {"client_id": str(condo["id"]), "equipment_id": str(dvr["id"]),
                                           "problem_description": "El DVR se reinicia solo cada pocos minutos."})
    await repairs.add_part(tech, str(old["id"]), product_id=product["FU-12V-2A"],
                           location_id=location["Camioneta 1"], quantity=1, note=None)
    await repairs.update_repair(tech, str(old["id"]), {"diagnosis": "Fuente con voltaje inestable (10.8V).",
                                                       "solution": "Cambio de fuente 12V 2A.",
                                                       "status": "resolved"})
    await repairs.open_repair(tech, {"client_id": str(condo["id"]), "equipment_id": str(dvr["id"]),
                                     "problem_description": "Canal 3 sin video desde ayer."})
    return True


async def _main() -> int:
    load_dotenv()
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("DATABASE_URL no está definido en .env.", file=sys.stderr)
        return 1
    database = Database(url, max_size=2)
    await database.connect()
    try:
        await database.migrate()
        created = await seed(database)
    finally:
        await database.close()
    print("Datos de demostración cargados." if created else "Ya había productos: no se cargó nada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
