"""Casos de uso del inventario.

Permisos (decididos con el equipo; ver README):
  * Catálogo, ubicaciones y movimientos manuales de stock: solo administradores.
  * Consultar disponibilidad, clientes, equipos e historial: cualquier usuario activo.
  * Registrar clientes, equipos y reparaciones: técnicos y administradores
    (el técnico está en campo y es quien conoce el equipo).
  * Modificar una reparación o agregarle repuestos: el técnico asignado o un administrador.
"""
from __future__ import annotations

from app.application.users import require_admin
from app.domain.errors import ConflictError, ForbiddenError, NotFoundError
from app.domain.inventory import MovementReason
from app.domain.ports import CatalogRepository, ClientRepository, RepairRepository, Row
from app.domain.users import AppUser


def _found(row: Row | None, what: str) -> Row:
    if row is None:
        raise NotFoundError(f"{what} not found")
    return row


class CatalogService:
    def __init__(self, repository: CatalogRepository):
        self._repo = repository

    async def search_products(self, actor: AppUser, *, query: str | None = None, category: str | None = None,
                              include_inactive: bool = False, low_stock_only: bool = False) -> list[Row]:
        # Los técnicos solo ven productos activos: los inactivos ya no se usan.
        return await self._repo.list_products(
            query=query, category=category,
            include_inactive=include_inactive and actor.is_admin, low_stock_only=low_stock_only,
        )

    async def get_product(self, actor: AppUser, product_id: str) -> Row:
        product = _found(await self._repo.get_product(product_id), "Product")
        if not product["is_active"] and not actor.is_admin:
            raise NotFoundError("Product not found")
        return product

    async def create_product(self, actor: AppUser, data: Row) -> Row:
        require_admin(actor)
        return await self._repo.create_product(data)

    async def update_product(self, actor: AppUser, product_id: str, data: Row) -> Row:
        require_admin(actor)
        return _found(await self._repo.update_product(product_id, data), "Product")

    async def list_locations(self, actor: AppUser, include_inactive: bool = False) -> list[Row]:
        return await self._repo.list_locations(include_inactive and actor.is_admin)

    async def create_location(self, actor: AppUser, data: Row) -> Row:
        require_admin(actor)
        return await self._repo.create_location(data)

    async def update_location(self, actor: AppUser, location_id: str, data: Row) -> Row:
        require_admin(actor)
        return _found(await self._repo.update_location(location_id, data), "Location")

    async def register_movement(self, actor: AppUser, *, product_id: str, location_id: str,
                                reason: MovementReason, quantity: int, note: str | None) -> Row:
        """Entrada (receipt), salida (issue) o ajuste a un conteo físico (adjustment).

        En receipt/issue `quantity` es la cantidad que entra o sale; en adjustment es
        la existencia contada, y el sistema calcula la diferencia.
        """
        require_admin(actor)
        if reason is MovementReason.ADJUSTMENT:
            return await self._repo.adjust_to(product_id=product_id, location_id=location_id,
                                              counted=quantity, actor_id=actor.id, note=note)
        if reason not in (MovementReason.RECEIPT, MovementReason.ISSUE):
            raise ConflictError("Ese motivo lo registra el sistema, no se crea a mano.", "INVALID_REASON")
        delta = quantity if reason is MovementReason.RECEIPT else -quantity
        return await self._repo.record_movement(product_id=product_id, location_id=location_id, delta=delta,
                                                reason=reason.value, actor_id=actor.id, note=note)

    async def transfer(self, actor: AppUser, *, product_id: str, from_location_id: str, to_location_id: str,
                       quantity: int, note: str | None) -> list[Row]:
        require_admin(actor)
        if from_location_id == to_location_id:
            raise ConflictError("El origen y el destino deben ser distintos.", "SAME_LOCATION")
        return await self._repo.transfer(product_id=product_id, from_location_id=from_location_id,
                                         to_location_id=to_location_id, quantity=quantity,
                                         actor_id=actor.id, note=note)

    async def list_movements(self, actor: AppUser, *, product_id: str | None, limit: int) -> list[Row]:
        return await self._repo.list_movements(product_id=product_id, limit=limit)


class ClientService:
    def __init__(self, repository: ClientRepository):
        self._repo = repository

    async def search_clients(self, actor: AppUser, *, query: str | None, limit: int, offset: int) -> list[Row]:
        return await self._repo.list_clients(query=query, limit=limit, offset=offset)

    async def get_client(self, actor: AppUser, client_id: str) -> Row:
        return _found(await self._repo.get_client(client_id), "Client")

    async def create_client(self, actor: AppUser, data: Row) -> Row:
        return await self._repo.create_client(data, actor.id)

    async def update_client(self, actor: AppUser, client_id: str, data: Row) -> Row:
        return _found(await self._repo.update_client(client_id, data), "Client")

    async def add_equipment(self, actor: AppUser, client_id: str, data: Row) -> Row:
        return await self._repo.create_equipment(client_id, data, actor.id)

    async def update_equipment(self, actor: AppUser, equipment_id: str, data: Row) -> Row:
        return _found(await self._repo.update_equipment(equipment_id, data), "Equipment")

    async def get_equipment(self, actor: AppUser, equipment_id: str) -> Row:
        return _found(await self._repo.get_equipment(equipment_id), "Equipment")


class RepairService:
    def __init__(self, repository: RepairRepository):
        self._repo = repository

    async def list_repairs(self, actor: AppUser, *, status: str | None = None, client_id: str | None = None,
                           equipment_id: str | None = None, only_mine: bool = False,
                           limit: int = 50, offset: int = 0) -> list[Row]:
        return await self._repo.list_repairs(
            status=status, client_id=client_id, equipment_id=equipment_id,
            technician_id=actor.id if only_mine else None, limit=limit, offset=offset,
        )

    async def get_repair(self, actor: AppUser, repair_id: str) -> Row:
        return _found(await self._repo.get_repair(repair_id), "Repair")

    async def open_repair(self, actor: AppUser, data: Row) -> Row:
        return await self._repo.create_repair(data, actor.id)

    async def _require_assigned(self, actor: AppUser, repair_id: str) -> None:
        repair = await self.get_repair(actor, repair_id)
        if not actor.is_admin and str(repair["technician_id"]) != actor.id:
            raise ForbiddenError("Only the assigned technician or an administrator can change this repair")

    async def update_repair(self, actor: AppUser, repair_id: str, data: Row) -> Row:
        await self._require_assigned(actor, repair_id)
        return await self._repo.update_repair(repair_id, data)

    async def add_part(self, actor: AppUser, repair_id: str, *, product_id: str, location_id: str,
                       quantity: int, note: str | None) -> Row:
        await self._require_assigned(actor, repair_id)
        return await self._repo.add_part(repair_id=repair_id, product_id=product_id, location_id=location_id,
                                         quantity=quantity, actor_id=actor.id, note=note)
