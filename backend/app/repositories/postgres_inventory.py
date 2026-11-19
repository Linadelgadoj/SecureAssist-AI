"""Inventario en PostgreSQL: catálogo, existencias, clientes, equipos y reparaciones.

Reglas que se garantizan aquí de forma atómica (no pueden vivir solo en Python
porque dos técnicos pueden actuar a la vez):
  * Cada cambio de existencia va acompañado de su movimiento, en la misma transacción.
  * Una salida solo se aplica si hay existencia suficiente (UPDATE ... WHERE quantity >= n).
  * Los repuestos solo se agregan a reparaciones abiertas (fila bloqueada con FOR UPDATE).
"""
from __future__ import annotations

from typing import Any

import asyncpg

from app.db.database import Database
from app.domain.errors import ConflictError, NotFoundError
from app.domain.inventory import EquipmentStatus, MovementReason, RepairStatus
from app.domain.ports import Row

# --------------------------------------------------------------------------- helpers


def _row(record: asyncpg.Record | None) -> Row | None:
    return dict(record) if record is not None else None


def _rows(records: list[asyncpg.Record]) -> list[Row]:
    return [dict(record) for record in records]


def _set_clause(data: Row, allowed: tuple[str, ...], start: int = 2) -> tuple[str, list[Any]]:
    """Construye 'col = $n' solo con columnas permitidas (nunca con texto del usuario)."""
    columns = [column for column in allowed if column in data]
    clause = ", ".join(f"{column} = ${index}" for index, column in enumerate(columns, start=start))
    return clause, [data[column] for column in columns]


def _insert(table: str, data: Row, allowed: tuple[str, ...], returning: str) -> tuple[str, list[Any]]:
    columns = [column for column in allowed if column in data]
    placeholders = ", ".join(f"${index}" for index in range(1, len(columns) + 1))
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) RETURNING {returning}"
    return sql, [data[column] for column in columns]


# --------------------------------------------------------------------------- catálogo

_PRODUCT_FIELDS = ("sku", "name", "category", "brand", "model", "unit", "min_stock", "description", "is_active")
_LOCATION_FIELDS = ("name", "kind", "is_active")

# Producto con existencia total y desglose por ubicación activa.
_PRODUCT_SELECT = """
    SELECT p.id, p.sku, p.name, p.category, p.brand, p.model, p.unit, p.min_stock,
           p.description, p.is_active, p.created_at, p.updated_at,
           coalesce(sum(s.quantity), 0)::int AS total_quantity,
           coalesce(sum(s.quantity), 0) <= p.min_stock AS is_low_stock,
           coalesce(
               jsonb_agg(jsonb_build_object('location_id', l.id, 'location_name', l.name,
                                            'location_kind', l.kind, 'quantity', s.quantity)
                         ORDER BY l.name) FILTER (WHERE s.quantity > 0),
               '[]'::jsonb) AS stock
      FROM products p
      LEFT JOIN stock_levels s ON s.product_id = p.id
      LEFT JOIN stock_locations l ON l.id = s.location_id AND l.is_active
"""
_PRODUCT_GROUP = " GROUP BY p.id"

_MOVEMENT_SELECT = """
    SELECT m.id, m.product_id, p.sku AS product_sku, p.name AS product_name,
           m.location_id, l.name AS location_name, m.quantity_delta, m.reason,
           m.repair_id, m.note, m.created_at, m.created_by, u.email AS created_by_email
      FROM stock_movements m
      JOIN products p ON p.id = m.product_id
      JOIN stock_locations l ON l.id = m.location_id
      JOIN app_users u ON u.id = m.created_by
"""


async def _apply_movement(conn: asyncpg.Connection, *, product_id: str, location_id: str, delta: int,
                          reason: MovementReason, actor_id: str, note: str | None,
                          repair_id: str | None = None) -> Row:
    """Aplica un movimiento dentro de una transacción ya abierta por el llamador."""
    product = await conn.fetchrow("SELECT is_active FROM products WHERE id = $1", product_id)
    location = await conn.fetchrow("SELECT is_active FROM stock_locations WHERE id = $1", location_id)
    if product is None or location is None:
        raise NotFoundError("Product or location not found")
    if not product["is_active"] or not location["is_active"]:
        raise ConflictError("El producto o la ubicación están inactivos.", "INACTIVE_ITEM")

    if delta > 0:
        await conn.execute(
            "INSERT INTO stock_levels (product_id, location_id, quantity) VALUES ($1, $2, $3)"
            " ON CONFLICT (product_id, location_id)"
            " DO UPDATE SET quantity = stock_levels.quantity + EXCLUDED.quantity, updated_at = now()",
            product_id, location_id, delta,
        )
    else:
        updated = await conn.fetchval(
            "UPDATE stock_levels SET quantity = quantity + $3, updated_at = now()"
            " WHERE product_id = $1 AND location_id = $2 AND quantity >= $4 RETURNING quantity",
            product_id, location_id, delta, -delta,
        )
        if updated is None:
            available = await conn.fetchval(
                "SELECT quantity FROM stock_levels WHERE product_id = $1 AND location_id = $2",
                product_id, location_id,
            ) or 0
            raise ConflictError(
                f"Existencia insuficiente: hay {available} y se necesitan {-delta}.", "INSUFFICIENT_STOCK"
            )

    movement_id = await conn.fetchval(
        "INSERT INTO stock_movements (product_id, location_id, quantity_delta, reason, repair_id, note, created_by)"
        " VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
        product_id, location_id, delta, reason.value, repair_id, note, actor_id,
    )
    return dict(await conn.fetchrow(_MOVEMENT_SELECT + " WHERE m.id = $1", movement_id))


class PostgresCatalogRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_products(self, *, query: str | None, category: str | None,
                            include_inactive: bool, low_stock_only: bool) -> list[Row]:
        conditions, args = [], []
        if not include_inactive:
            conditions.append("p.is_active")
        if category:
            args.append(category)
            conditions.append(f"p.category = ${len(args)}")
        if query:
            args.append(f"%{query}%")
            n = len(args)
            conditions.append(
                f"(p.name ILIKE ${n} OR p.sku ILIKE ${n} OR p.brand ILIKE ${n} OR p.model ILIKE ${n})"
            )
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        having = " HAVING coalesce(sum(s.quantity), 0) <= p.min_stock" if low_stock_only else ""
        async with self._db.connection() as conn:
            return _rows(await conn.fetch(_PRODUCT_SELECT + where + _PRODUCT_GROUP + having
                                          + " ORDER BY p.name LIMIT 500", *args))

    async def get_product(self, product_id: str) -> Row | None:
        async with self._db.connection() as conn:
            return _row(await conn.fetchrow(_PRODUCT_SELECT + " WHERE p.id = $1" + _PRODUCT_GROUP, product_id))

    async def create_product(self, data: Row) -> Row:
        sql, args = _insert("products", data, _PRODUCT_FIELDS, "id")
        async with self._db.connection() as conn:
            try:
                product_id = await conn.fetchval(sql, *args)
            except asyncpg.exceptions.UniqueViolationError as exc:
                raise ConflictError("Ya existe un producto con ese SKU.", "SKU_IN_USE") from exc
        return await self.get_product(str(product_id))

    async def update_product(self, product_id: str, data: Row) -> Row | None:
        clause, args = _set_clause(data, _PRODUCT_FIELDS)
        async with self._db.connection() as conn:
            try:
                found = await conn.fetchval(
                    f"UPDATE products SET {clause}, updated_at = now() WHERE id = $1 RETURNING id", product_id, *args
                )
            except asyncpg.exceptions.UniqueViolationError as exc:
                raise ConflictError("Ya existe un producto con ese SKU.", "SKU_IN_USE") from exc
        return await self.get_product(product_id) if found else None

    async def list_locations(self, include_inactive: bool) -> list[Row]:
        where = "" if include_inactive else " WHERE is_active"
        async with self._db.connection() as conn:
            return _rows(await conn.fetch(
                f"SELECT id, name, kind, is_active, created_at FROM stock_locations{where} ORDER BY name"))

    async def create_location(self, data: Row) -> Row:
        sql, args = _insert("stock_locations", data, _LOCATION_FIELDS, "id, name, kind, is_active, created_at")
        async with self._db.connection() as conn:
            try:
                return dict(await conn.fetchrow(sql, *args))
            except asyncpg.exceptions.UniqueViolationError as exc:
                raise ConflictError("Ya existe una ubicación con ese nombre.", "LOCATION_IN_USE") from exc

    async def update_location(self, location_id: str, data: Row) -> Row | None:
        clause, args = _set_clause(data, _LOCATION_FIELDS)
        async with self._db.connection() as conn:
            try:
                return _row(await conn.fetchrow(
                    f"UPDATE stock_locations SET {clause} WHERE id = $1"
                    " RETURNING id, name, kind, is_active, created_at", location_id, *args))
            except asyncpg.exceptions.UniqueViolationError as exc:
                raise ConflictError("Ya existe una ubicación con ese nombre.", "LOCATION_IN_USE") from exc

    async def record_movement(self, *, product_id: str, location_id: str, delta: int, reason: str,
                              actor_id: str, note: str | None) -> Row:
        async with self._db.transaction() as conn:
            return await _apply_movement(conn, product_id=product_id, location_id=location_id, delta=delta,
                                         reason=MovementReason(reason), actor_id=actor_id, note=note)

    async def adjust_to(self, *, product_id: str, location_id: str, counted: int,
                        actor_id: str, note: str | None) -> Row:
        async with self._db.transaction() as conn:
            current = await conn.fetchval(
                "SELECT quantity FROM stock_levels WHERE product_id = $1 AND location_id = $2 FOR UPDATE",
                product_id, location_id,
            ) or 0
            if counted == current:
                raise ConflictError(f"La existencia ya es {current}; no hay nada que ajustar.", "NO_CHANGE")
            return await _apply_movement(conn, product_id=product_id, location_id=location_id,
                                         delta=counted - current, reason=MovementReason.ADJUSTMENT,
                                         actor_id=actor_id, note=note)

    async def transfer(self, *, product_id: str, from_location_id: str, to_location_id: str,
                       quantity: int, actor_id: str, note: str | None) -> list[Row]:
        async with self._db.transaction() as conn:
            out = await _apply_movement(conn, product_id=product_id, location_id=from_location_id,
                                        delta=-quantity, reason=MovementReason.TRANSFER_OUT,
                                        actor_id=actor_id, note=note)
            into = await _apply_movement(conn, product_id=product_id, location_id=to_location_id,
                                         delta=quantity, reason=MovementReason.TRANSFER_IN,
                                         actor_id=actor_id, note=note)
        return [out, into]

    async def list_movements(self, *, product_id: str | None, limit: int) -> list[Row]:
        async with self._db.connection() as conn:
            if product_id:
                records = await conn.fetch(_MOVEMENT_SELECT + " WHERE m.product_id = $1"
                                           " ORDER BY m.created_at DESC, m.id LIMIT $2", product_id, limit)
            else:
                records = await conn.fetch(_MOVEMENT_SELECT + " ORDER BY m.created_at DESC, m.id LIMIT $1", limit)
        return _rows(records)


# --------------------------------------------------------------------------- clientes y equipos

_CLIENT_FIELDS = ("name", "document_id", "phone", "email", "address", "notes")
_EQUIPMENT_FIELDS = ("product_id", "equipment_type", "brand", "model", "serial_number",
                     "site_description", "installed_on", "status", "notes")
_CLIENT_COLUMNS = "c.id, c.name, c.document_id, c.phone, c.email, c.address, c.notes, c.created_at, c.updated_at"
_EQUIPMENT_COLUMNS = ("e.id, e.client_id, e.product_id, e.equipment_type, e.brand, e.model, e.serial_number,"
                      " e.site_description, e.installed_on, e.status, e.notes, e.created_at, e.updated_at")


def _equipment_conflict(exc: Exception) -> ConflictError:
    return ConflictError("Ya existe un equipo de esa marca con ese número de serie.", "SERIAL_IN_USE")


class PostgresClientRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_clients(self, *, query: str | None, limit: int, offset: int) -> list[Row]:
        args: list[Any] = []
        where = ""
        if query:
            args.append(f"%{query}%")
            where = " WHERE c.name ILIKE $1 OR c.document_id ILIKE $1 OR c.phone ILIKE $1 OR c.address ILIKE $1"
        args += [limit, offset]
        async with self._db.connection() as conn:
            return _rows(await conn.fetch(
                f"""
                SELECT {_CLIENT_COLUMNS},
                       (SELECT count(*) FROM installed_equipment e
                         WHERE e.client_id = c.id AND e.status <> 'removed')::int AS equipment_count,
                       (SELECT count(*) FROM repairs r
                         WHERE r.client_id = c.id AND r.status IN ('open', 'in_progress'))::int AS open_repairs
                  FROM clients c{where}
                 ORDER BY lower(c.name), c.id
                 LIMIT ${len(args) - 1} OFFSET ${len(args)}
                """, *args))

    async def get_client(self, client_id: str) -> Row | None:
        async with self._db.connection() as conn:
            client = _row(await conn.fetchrow(f"SELECT {_CLIENT_COLUMNS} FROM clients c WHERE c.id = $1", client_id))
            if client is None:
                return None
            client["equipment"] = _rows(await conn.fetch(
                f"SELECT {_EQUIPMENT_COLUMNS} FROM installed_equipment e WHERE e.client_id = $1"
                " ORDER BY e.status = 'removed', e.equipment_type, e.created_at", client_id))
        return client

    async def create_client(self, data: Row, actor_id: str) -> Row:
        sql, args = _insert("clients", {**data, "created_by": actor_id}, _CLIENT_FIELDS + ("created_by",), "id")
        async with self._db.connection() as conn:
            client_id = await conn.fetchval(sql, *args)
        return await self.get_client(str(client_id))

    async def update_client(self, client_id: str, data: Row) -> Row | None:
        clause, args = _set_clause(data, _CLIENT_FIELDS)
        async with self._db.connection() as conn:
            found = await conn.fetchval(
                f"UPDATE clients SET {clause}, updated_at = now() WHERE id = $1 RETURNING id", client_id, *args)
        return await self.get_client(client_id) if found else None

    async def create_equipment(self, client_id: str, data: Row, actor_id: str) -> Row:
        values = {**data, "client_id": client_id, "created_by": actor_id}
        sql, args = _insert("installed_equipment", values, _EQUIPMENT_FIELDS + ("client_id", "created_by"), "id")
        async with self._db.connection() as conn:
            try:
                equipment_id = await conn.fetchval(sql, *args)
            except asyncpg.exceptions.ForeignKeyViolationError as exc:
                raise NotFoundError("Client or product not found") from exc
            except asyncpg.exceptions.UniqueViolationError as exc:
                raise _equipment_conflict(exc) from exc
        return await self.get_equipment(str(equipment_id))

    async def update_equipment(self, equipment_id: str, data: Row) -> Row | None:
        clause, args = _set_clause(data, _EQUIPMENT_FIELDS)
        async with self._db.connection() as conn:
            try:
                found = await conn.fetchval(
                    f"UPDATE installed_equipment SET {clause}, updated_at = now() WHERE id = $1 RETURNING id",
                    equipment_id, *args)
            except asyncpg.exceptions.ForeignKeyViolationError as exc:
                raise NotFoundError("Product not found") from exc
            except asyncpg.exceptions.UniqueViolationError as exc:
                raise _equipment_conflict(exc) from exc
        return await self.get_equipment(equipment_id) if found else None

    async def get_equipment(self, equipment_id: str) -> Row | None:
        async with self._db.connection() as conn:
            equipment = _row(await conn.fetchrow(
                f"SELECT {_EQUIPMENT_COLUMNS}, c.name AS client_name FROM installed_equipment e"
                " JOIN clients c ON c.id = e.client_id WHERE e.id = $1", equipment_id))
            if equipment is None:
                return None
            equipment["repairs"] = _rows(await conn.fetch(
                _REPAIR_SELECT + " WHERE r.equipment_id = $1 ORDER BY r.opened_at DESC", equipment_id))
        return equipment


# --------------------------------------------------------------------------- reparaciones

_REPAIR_FIELDS = ("diagnosis", "solution", "status")
_REPAIR_SELECT = """
    SELECT r.id, r.client_id, c.name AS client_name, r.equipment_id,
           CASE WHEN e.id IS NULL THEN NULL
                ELSE concat_ws(' ', e.equipment_type, e.brand, e.model) END AS equipment_label,
           e.serial_number AS equipment_serial,
           r.technician_id, u.email AS technician_email, u.full_name AS technician_name,
           r.conversation_id, r.problem_description, r.diagnosis, r.solution, r.status,
           r.opened_at, r.closed_at, r.updated_at,
           (SELECT coalesce(sum(-m.quantity_delta), 0) FROM stock_movements m
             WHERE m.repair_id = r.id)::int AS parts_count
      FROM repairs r
      JOIN clients c ON c.id = r.client_id
      LEFT JOIN installed_equipment e ON e.id = r.equipment_id
      JOIN app_users u ON u.id = r.technician_id
"""


class PostgresRepairRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_repairs(self, *, status: str | None, client_id: str | None, equipment_id: str | None,
                           technician_id: str | None, limit: int, offset: int) -> list[Row]:
        conditions, args = [], []
        for column, value in (("r.status", status), ("r.client_id", client_id),
                              ("r.equipment_id", equipment_id), ("r.technician_id", technician_id)):
            if value:
                args.append(value)
                conditions.append(f"{column} = ${len(args)}")
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        args += [limit, offset]
        async with self._db.connection() as conn:
            return _rows(await conn.fetch(
                _REPAIR_SELECT + where
                + f" ORDER BY r.status IN ('resolved', 'cancelled'), r.opened_at DESC, r.id"
                  f" LIMIT ${len(args) - 1} OFFSET ${len(args)}", *args))

    async def get_repair(self, repair_id: str) -> Row | None:
        async with self._db.connection() as conn:
            repair = _row(await conn.fetchrow(_REPAIR_SELECT + " WHERE r.id = $1", repair_id))
            if repair is None:
                return None
            repair["parts"] = _rows(await conn.fetch(
                _MOVEMENT_SELECT + " WHERE m.repair_id = $1 ORDER BY m.created_at, m.id", repair_id))
        return repair

    async def create_repair(self, data: Row, technician_id: str) -> Row:
        async with self._db.transaction() as conn:
            if not await conn.fetchval("SELECT EXISTS (SELECT 1 FROM clients WHERE id = $1)", data["client_id"]):
                raise NotFoundError("Client not found")
            equipment_id = data.get("equipment_id")
            if equipment_id:
                owner = await conn.fetchval(
                    "SELECT client_id FROM installed_equipment WHERE id = $1 FOR UPDATE", equipment_id)
                if owner is None:
                    raise NotFoundError("Equipment not found")
                if str(owner) != str(data["client_id"]):
                    raise ConflictError("El equipo no pertenece a ese cliente.", "EQUIPMENT_CLIENT_MISMATCH")
            conversation_id = data.get("conversation_id")
            if conversation_id and not await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM conversations WHERE id = $1 AND owner_user_id = $2)",
                    conversation_id, technician_id):
                # Las conversaciones son privadas: solo se puede enlazar una propia.
                raise NotFoundError("Conversation not found")
            repair_id = await conn.fetchval(
                "INSERT INTO repairs (client_id, equipment_id, technician_id, conversation_id, problem_description)"
                " VALUES ($1, $2, $3, $4, $5) RETURNING id",
                data["client_id"], equipment_id, technician_id, conversation_id, data["problem_description"])
            if equipment_id:
                await conn.execute(
                    "UPDATE installed_equipment SET status = $2, updated_at = now() WHERE id = $1",
                    equipment_id, EquipmentStatus.IN_REPAIR.value)
        return await self.get_repair(str(repair_id))

    async def update_repair(self, repair_id: str, data: Row) -> Row:
        async with self._db.transaction() as conn:
            current = await conn.fetchrow(
                "SELECT status, equipment_id FROM repairs WHERE id = $1 FOR UPDATE", repair_id)
            if current is None:
                raise NotFoundError("Repair not found")
            if RepairStatus(current["status"]).is_closed:
                raise ConflictError("La reparación ya está cerrada.", "REPAIR_CLOSED")
            clause, args = _set_clause(data, _REPAIR_FIELDS)
            new_status = RepairStatus(data.get("status", current["status"]))
            closed_sql = ", closed_at = now()" if new_status.is_closed else ""
            await conn.execute(
                f"UPDATE repairs SET {clause}{closed_sql}, updated_at = now() WHERE id = $1", repair_id, *args)
            if new_status.is_closed and current["equipment_id"]:
                # Al cerrar, el equipo vuelve a operar, salvo que el técnico lo
                # haya marcado manualmente con otro estado mientras tanto.
                await conn.execute(
                    "UPDATE installed_equipment SET status = $2, updated_at = now()"
                    " WHERE id = $1 AND status = $3",
                    current["equipment_id"], EquipmentStatus.OPERATIONAL.value, EquipmentStatus.IN_REPAIR.value)
        return await self.get_repair(repair_id)

    async def add_part(self, *, repair_id: str, product_id: str, location_id: str,
                       quantity: int, actor_id: str, note: str | None) -> Row:
        async with self._db.transaction() as conn:
            status = await conn.fetchval("SELECT status FROM repairs WHERE id = $1 FOR UPDATE", repair_id)
            if status is None:
                raise NotFoundError("Repair not found")
            if RepairStatus(status).is_closed:
                raise ConflictError("La reparación ya está cerrada.", "REPAIR_CLOSED")
            movement = await _apply_movement(conn, product_id=product_id, location_id=location_id,
                                             delta=-quantity, reason=MovementReason.REPAIR,
                                             actor_id=actor_id, note=note, repair_id=repair_id)
            if status == RepairStatus.OPEN.value:
                await conn.execute(
                    "UPDATE repairs SET status = 'in_progress', updated_at = now() WHERE id = $1", repair_id)
        return movement
