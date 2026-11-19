"""Rutas HTTP del inventario. Solo traducen HTTP <-> casos de uso; los permisos
y reglas viven en app.application.inventory."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.application.inventory import CatalogService, ClientService, RepairService
from app.dependencies.auth import get_current_account
from app.dependencies.services import get_catalog_service, get_client_service, get_repair_service
from app.domain.inventory import MovementReason
from app.domain.users import AppUser
from app.schemas.inventory import (
    ClientCreate, ClientDetail, ClientSummary, ClientUpdate, EquipmentCreate, EquipmentDetail,
    EquipmentUpdate, LocationCreate, LocationResponse, LocationUpdate, MovementCreate,
    MovementResponse, PartCreate, ProductCreate, ProductResponse, ProductUpdate, RepairCreate,
    RepairDetail, RepairStatus, RepairSummary, RepairUpdate, TransferCreate,
)

router = APIRouter(tags=["inventory"])

Account = Depends(get_current_account)
Catalog = Depends(get_catalog_service)
Clients = Depends(get_client_service)
Repairs = Depends(get_repair_service)


# --------------------------------------------------------------------------- productos

@router.get("/products", response_model=list[ProductResponse], summary="Buscar productos y su disponibilidad")
async def list_products(
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=60),
    include_inactive: bool = False,
    low_stock: bool = False,
    actor: AppUser = Account, service: CatalogService = Catalog,
):
    return await service.search_products(actor, query=q, category=category,
                                         include_inactive=include_inactive, low_stock_only=low_stock)


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(product_id: UUID, actor: AppUser = Account, service: CatalogService = Catalog):
    return await service.get_product(actor, str(product_id))


@router.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(payload: ProductCreate, actor: AppUser = Account, service: CatalogService = Catalog):
    return await service.create_product(actor, payload.to_data())


@router.patch("/products/{product_id}", response_model=ProductResponse)
async def update_product(product_id: UUID, payload: ProductUpdate,
                         actor: AppUser = Account, service: CatalogService = Catalog):
    return await service.update_product(actor, str(product_id), payload.to_data())


# --------------------------------------------------------------------------- ubicaciones

@router.get("/locations", response_model=list[LocationResponse])
async def list_locations(include_inactive: bool = False, actor: AppUser = Account,
                         service: CatalogService = Catalog):
    return await service.list_locations(actor, include_inactive)


@router.post("/locations", response_model=LocationResponse, status_code=201)
async def create_location(payload: LocationCreate, actor: AppUser = Account, service: CatalogService = Catalog):
    return await service.create_location(actor, payload.to_data())


@router.patch("/locations/{location_id}", response_model=LocationResponse)
async def update_location(location_id: UUID, payload: LocationUpdate,
                          actor: AppUser = Account, service: CatalogService = Catalog):
    return await service.update_location(actor, str(location_id), payload.to_data())


# --------------------------------------------------------------------------- movimientos de stock

@router.get("/stock/movements", response_model=list[MovementResponse])
async def list_movements(product_id: UUID | None = None, limit: int = Query(default=50, ge=1, le=200),
                         actor: AppUser = Account, service: CatalogService = Catalog):
    return await service.list_movements(actor, product_id=str(product_id) if product_id else None, limit=limit)


@router.post("/stock/movements", response_model=MovementResponse, status_code=201,
             summary="Entrada, salida o ajuste por conteo (solo administradores)")
async def create_movement(payload: MovementCreate, actor: AppUser = Account, service: CatalogService = Catalog):
    return await service.register_movement(
        actor, product_id=str(payload.product_id), location_id=str(payload.location_id),
        reason=MovementReason(payload.reason), quantity=payload.quantity, note=payload.note,
    )


@router.post("/stock/transfers", response_model=list[MovementResponse], status_code=201)
async def create_transfer(payload: TransferCreate, actor: AppUser = Account, service: CatalogService = Catalog):
    return await service.transfer(
        actor, product_id=str(payload.product_id), from_location_id=str(payload.from_location_id),
        to_location_id=str(payload.to_location_id), quantity=payload.quantity, note=payload.note,
    )


# --------------------------------------------------------------------------- clientes y equipos

@router.get("/clients", response_model=list[ClientSummary])
async def list_clients(q: str | None = Query(default=None, max_length=100),
                       limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
                       actor: AppUser = Account, service: ClientService = Clients):
    return await service.search_clients(actor, query=q, limit=limit, offset=offset)


@router.post("/clients", response_model=ClientDetail, status_code=201)
async def create_client(payload: ClientCreate, actor: AppUser = Account, service: ClientService = Clients):
    return await service.create_client(actor, payload.to_data())


@router.get("/clients/{client_id}", response_model=ClientDetail)
async def get_client(client_id: UUID, actor: AppUser = Account, service: ClientService = Clients):
    return await service.get_client(actor, str(client_id))


@router.patch("/clients/{client_id}", response_model=ClientDetail)
async def update_client(client_id: UUID, payload: ClientUpdate,
                        actor: AppUser = Account, service: ClientService = Clients):
    return await service.update_client(actor, str(client_id), payload.to_data())


@router.post("/clients/{client_id}/equipment", response_model=EquipmentDetail, status_code=201)
async def add_equipment(client_id: UUID, payload: EquipmentCreate,
                        actor: AppUser = Account, service: ClientService = Clients):
    data = payload.to_data()
    if data.get("product_id"):
        data["product_id"] = str(data["product_id"])
    return await service.add_equipment(actor, str(client_id), data)


@router.get("/equipment/{equipment_id}", response_model=EquipmentDetail,
            summary="Equipo instalado con su historial de reparaciones")
async def get_equipment(equipment_id: UUID, actor: AppUser = Account, service: ClientService = Clients):
    return await service.get_equipment(actor, str(equipment_id))


@router.patch("/equipment/{equipment_id}", response_model=EquipmentDetail)
async def update_equipment(equipment_id: UUID, payload: EquipmentUpdate,
                           actor: AppUser = Account, service: ClientService = Clients):
    data = payload.to_data()
    if data.get("product_id"):
        data["product_id"] = str(data["product_id"])
    return await service.update_equipment(actor, str(equipment_id), data)


# --------------------------------------------------------------------------- reparaciones

@router.get("/repairs", response_model=list[RepairSummary])
async def list_repairs(status: RepairStatus | None = None, client_id: UUID | None = None,
                       equipment_id: UUID | None = None, mine: bool = False,
                       limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
                       actor: AppUser = Account, service: RepairService = Repairs):
    return await service.list_repairs(
        actor, status=status, client_id=str(client_id) if client_id else None,
        equipment_id=str(equipment_id) if equipment_id else None, only_mine=mine, limit=limit, offset=offset,
    )


@router.post("/repairs", response_model=RepairDetail, status_code=201)
async def open_repair(payload: RepairCreate, actor: AppUser = Account, service: RepairService = Repairs):
    data = {key: (str(value) if isinstance(value, UUID) else value) for key, value in payload.to_data().items()}
    return await service.open_repair(actor, data)


@router.get("/repairs/{repair_id}", response_model=RepairDetail)
async def get_repair(repair_id: UUID, actor: AppUser = Account, service: RepairService = Repairs):
    return await service.get_repair(actor, str(repair_id))


@router.patch("/repairs/{repair_id}", response_model=RepairDetail)
async def update_repair(repair_id: UUID, payload: RepairUpdate,
                        actor: AppUser = Account, service: RepairService = Repairs):
    return await service.update_repair(actor, str(repair_id), payload.to_data())


@router.post("/repairs/{repair_id}/parts", response_model=MovementResponse, status_code=201,
             summary="Registrar un repuesto usado (descuenta del stock)")
async def add_part(repair_id: UUID, payload: PartCreate, actor: AppUser = Account,
                   service: RepairService = Repairs):
    return await service.add_part(actor, str(repair_id), product_id=str(payload.product_id),
                                  location_id=str(payload.location_id), quantity=payload.quantity,
                                  note=payload.note)
