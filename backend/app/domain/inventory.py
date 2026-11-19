"""Vocabulario del inventario: estados y motivos válidos (coinciden con los CHECK de SQL)."""
from __future__ import annotations

from enum import StrEnum


class LocationKind(StrEnum):
    WAREHOUSE = "warehouse"
    VEHICLE = "vehicle"
    OTHER = "other"


class MovementReason(StrEnum):
    RECEIPT = "receipt"          # entrada (compra, devolución a bodega)
    ISSUE = "issue"              # salida manual (venta, baja, pérdida)
    ADJUSTMENT = "adjustment"    # corrección tras conteo físico
    REPAIR = "repair"            # repuesto usado en una reparación
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


# Motivos que un administrador puede registrar directamente; el resto los genera el sistema.
MANUAL_REASONS = (MovementReason.RECEIPT, MovementReason.ISSUE)


class EquipmentStatus(StrEnum):
    OPERATIONAL = "operational"
    IN_REPAIR = "in_repair"
    OUT_OF_SERVICE = "out_of_service"
    REMOVED = "removed"


class RepairStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"

    @property
    def is_closed(self) -> bool:
        return self in (RepairStatus.RESOLVED, RepairStatus.CANCELLED)
