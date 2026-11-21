"""Contratos HTTP del inventario: validación de entrada y forma de las respuestas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = lambda max_length: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)]  # noqa: E731
OptionalText = lambda max_length: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=max_length)]  # noqa: E731

LocationKind = Literal["warehouse", "vehicle", "other"]
EquipmentStatus = Literal["operational", "in_repair", "out_of_service", "removed"]
RepairStatus = Literal["open", "in_progress", "resolved", "cancelled"]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_data(self) -> dict:
        """Solo los campos enviados; los textos vacíos se guardan como NULL."""
        data = self.model_dump(exclude_unset=True)
        return {key: (None if value == "" else value) for key, value in data.items()}


class _Update(_Input):
    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Envía al menos un campo para actualizar.")
        return self


# --------------------------------------------------------------------------- productos

class ProductCreate(_Input):
    sku: Text(60)
    name: Text(200)
    category: Text(60)
    brand: OptionalText(100) = None
    model: OptionalText(100) = None
    unit: Text(30) = "unidad"
    min_stock: int = Field(default=0, ge=0, le=1_000_000)
    description: OptionalText(2000) = None


class ProductUpdate(_Update):
    sku: Text(60) | None = None
    name: Text(200) | None = None
    category: Text(60) | None = None
    brand: OptionalText(100) = None
    model: OptionalText(100) = None
    unit: Text(30) | None = None
    min_stock: int | None = Field(default=None, ge=0, le=1_000_000)
    description: OptionalText(2000) = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def no_null_required(self):
        for name in ("sku", "name", "category", "unit", "min_stock", "is_active"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} no puede ser nulo.")
        return self


class StockAtLocation(BaseModel):
    location_id: UUID
    location_name: str
    location_kind: LocationKind
    quantity: int


class ProductResponse(BaseModel):
    id: UUID
    sku: str
    name: str
    category: str
    brand: str | None
    model: str | None
    unit: str
    min_stock: int
    description: str | None
    is_active: bool
    total_quantity: int
    is_low_stock: bool
    stock: list[StockAtLocation]
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- ubicaciones y stock

class LocationCreate(_Input):
    name: Text(100)
    kind: LocationKind = "warehouse"


class LocationUpdate(_Update):
    name: Text(100) | None = None
    kind: LocationKind | None = None
    is_active: bool | None = None


class LocationResponse(BaseModel):
    id: UUID
    name: str
    kind: LocationKind
    is_active: bool
    created_at: datetime


class MovementCreate(_Input):
    product_id: UUID
    location_id: UUID
    # receipt: entra `quantity`; issue: sale `quantity`; adjustment: `quantity` es el conteo físico.
    reason: Literal["receipt", "issue", "adjustment"]
    quantity: int = Field(ge=0, le=1_000_000)
    note: OptionalText(500) = None

    @model_validator(mode="after")
    def positive_unless_adjustment(self):
        if self.reason != "adjustment" and self.quantity == 0:
            raise ValueError("La cantidad debe ser mayor que cero.")
        return self


class TransferCreate(_Input):
    product_id: UUID
    from_location_id: UUID
    to_location_id: UUID
    quantity: int = Field(gt=0, le=1_000_000)
    note: OptionalText(500) = None


class MovementResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_sku: str
    product_name: str
    location_id: UUID
    location_name: str
    quantity_delta: int
    reason: str
    repair_id: UUID | None
    note: str | None
    created_at: datetime
    created_by_email: str


# --------------------------------------------------------------------------- clientes y equipos

class ClientCreate(_Input):
    name: Text(200)
    document_id: OptionalText(30) = None
    phone: OptionalText(30) = None
    email: OptionalText(320) = None
    address: OptionalText(300) = None
    notes: OptionalText(2000) = None


class ClientUpdate(_Update):
    name: Text(200) | None = None
    document_id: OptionalText(30) = None
    phone: OptionalText(30) = None
    email: OptionalText(320) = None
    address: OptionalText(300) = None
    notes: OptionalText(2000) = None

    @model_validator(mode="after")
    def name_not_null(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name no puede ser nulo.")
        return self


class EquipmentCreate(_Input):
    equipment_type: Text(60)
    product_id: UUID | None = None
    brand: OptionalText(100) = None
    model: OptionalText(100) = None
    serial_number: OptionalText(100) = None
    site_description: OptionalText(300) = None
    installed_on: date | None = None
    status: EquipmentStatus = "operational"
    notes: OptionalText(2000) = None


class EquipmentUpdate(_Update):
    equipment_type: Text(60) | None = None
    product_id: UUID | None = None
    brand: OptionalText(100) = None
    model: OptionalText(100) = None
    serial_number: OptionalText(100) = None
    site_description: OptionalText(300) = None
    installed_on: date | None = None
    status: EquipmentStatus | None = None
    notes: OptionalText(2000) = None

    @model_validator(mode="after")
    def required_not_null(self):
        for name in ("equipment_type", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} no puede ser nulo.")
        return self


class EquipmentResponse(BaseModel):
    id: UUID
    client_id: UUID
    product_id: UUID | None
    equipment_type: str
    brand: str | None
    model: str | None
    serial_number: str | None
    site_description: str | None
    installed_on: date | None
    status: EquipmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ClientSummary(BaseModel):
    id: UUID
    name: str
    document_id: str | None
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    equipment_count: int
    open_repairs: int


class ClientDetail(BaseModel):
    id: UUID
    name: str
    document_id: str | None
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    equipment: list[EquipmentResponse]


# --------------------------------------------------------------------------- reparaciones

class RepairCreate(_Input):
    client_id: UUID
    equipment_id: UUID | None = None
    conversation_id: UUID | None = None
    problem_description: Text(4000)


class RepairUpdate(_Update):
    diagnosis: OptionalText(4000) = None
    solution: OptionalText(4000) = None
    status: RepairStatus | None = None

    @model_validator(mode="after")
    def status_not_null(self):
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status no puede ser nulo.")
        return self


class PartCreate(_Input):
    product_id: UUID
    location_id: UUID
    quantity: int = Field(gt=0, le=10_000)
    note: OptionalText(500) = None


class RepairSummary(BaseModel):
    id: UUID
    client_id: UUID
    client_name: str
    equipment_id: UUID | None
    equipment_label: str | None
    equipment_serial: str | None
    technician_id: UUID
    technician_email: str
    technician_name: str | None
    conversation_id: UUID | None
    problem_description: str
    diagnosis: str | None
    solution: str | None
    status: RepairStatus
    opened_at: datetime
    closed_at: datetime | None
    parts_count: int


class RepairDetail(RepairSummary):
    parts: list[MovementResponse]


class EquipmentDetail(EquipmentResponse):
    client_name: str
    repairs: list[RepairSummary]
