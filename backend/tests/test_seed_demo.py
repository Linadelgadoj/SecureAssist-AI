"""El script de demostración funciona sobre una base vacía y no duplica datos."""
import asyncio

from app.db.database import Database
from app.db.seed_demo import PRODUCTS, seed
from postgres_support import TEST_DATABASE_URL, requires_postgres, reset_database

pytestmark = requires_postgres


def test_seed_loads_once_and_respects_stock_rules():
    reset_database()

    async def run():
        database = Database(TEST_DATABASE_URL, max_size=2)
        await database.connect()
        try:
            await database.migrate()
            first = await seed(database)
            second = await seed(database)
            async with database.connection() as conn:
                counts = {table: await conn.fetchval(f"SELECT count(*) FROM {table}")
                          for table in ("app_users", "products", "clients", "installed_equipment", "repairs")}
                roles = dict(await conn.fetch("SELECT email, role FROM app_users"))
                power = await conn.fetchval(
                    "SELECT sum(quantity) FROM stock_levels s JOIN products p ON p.id = s.product_id"
                    " WHERE p.sku = 'FU-12V-2A'")
        finally:
            await database.close()
        return first, second, counts, roles, power

    first, second, counts, roles, power = asyncio.run(run())
    assert (first, second) == (True, False)
    assert counts == {"app_users": 2, "products": len(PRODUCTS), "clients": 2, "installed_equipment": 3, "repairs": 2}
    assert roles == {"dev@localhost": "admin", "tecnico@localhost": "technician"}
    assert power == 19  # 20 recibidas - 1 usada en la reparación resuelta
