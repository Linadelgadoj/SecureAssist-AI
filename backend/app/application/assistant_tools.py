"""Herramientas de SOLO LECTURA que el asistente puede usar durante una conversación.

El modelo nunca escribe en la base: puede consultar existencias e historial de
equipos, pero registrar repuestos o reparaciones sigue siendo una acción del
técnico en la interfaz. Los argumentos vienen del modelo (no confiables): se
recortan y validan antes de usarlos.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from app.domain.assistant import ToolSpec
from app.domain.ports import CatalogRepository, ClientRepository, Row

MAX_QUERY = 80
MAX_RESULTS = 6
# Palabras que no ayudan a encontrar un repuesto ("fuente DE poder PARA cámara").
_STOPWORDS = {"de", "del", "la", "el", "los", "las", "para", "con", "un", "una", "y", "o", "en", "por", "poder", "tipo"}

INVENTORY_TOOL = ToolSpec(
    name="consultar_inventario",
    description=("Busca repuestos o equipos en el inventario de la empresa y devuelve cuántas unidades "
                 "hay disponibles en cada ubicación (bodegas y vehículos). Úsala cuando el técnico pregunte "
                 "si hay un repuesto o cuando recomiendes reemplazar una pieza."),
    parameters={"type": "object", "properties": {
        "busqueda": {"type": "string", "description": "Qué buscar: tipo, marca, modelo o código. Ej.: 'fuente 12V'."},
    }, "required": ["busqueda"]},
)
EQUIPMENT_TOOL = ToolSpec(
    name="historial_equipo",
    description=("Busca equipos instalados en clientes por número de serie, marca, modelo o nombre del "
                 "cliente, y devuelve su estado y sus reparaciones anteriores con diagnóstico y solución."),
    parameters={"type": "object", "properties": {
        "busqueda": {"type": "string", "description": "Serial, marca, modelo o nombre del cliente."},
    }, "required": ["busqueda"]},
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", _normalize(text)) if len(t) > 1 and t not in _STOPWORDS]


def rank_products(products: list[Row], query: str) -> list[Row]:
    """Ordena por cuántas palabras de la búsqueda aparecen en el producto (al menos una)."""
    wanted = _tokens(query)
    scored = []
    for product in products:
        haystack = _normalize(" ".join(str(product.get(key) or "")
                                       for key in ("name", "sku", "brand", "model", "category")))
        score = sum(1 for token in wanted if token in haystack)
        if score:
            scored.append((score, product))
    scored.sort(key=lambda item: (-item[0], -item[1].get("total_quantity", 0)))
    return [product for _, product in scored[:MAX_RESULTS]]


class AssistantTools:
    def __init__(self, catalog: CatalogRepository | None, clients: ClientRepository | None):
        self._catalog = catalog
        self._clients = clients

    @property
    def specs(self) -> list[ToolSpec]:
        specs = []
        if self._catalog is not None:
            specs.append(INVENTORY_TOOL)
        if self._clients is not None:
            specs.append(EQUIPMENT_TOOL)
        return specs

    async def run(self, name: str, arguments: dict[str, Any]) -> str:
        """Ejecuta la herramienta y devuelve JSON compacto para el modelo. Nunca lanza."""
        query = arguments.get("busqueda")
        if not isinstance(query, str) or not query.strip():
            return json.dumps({"error": "Falta el texto de búsqueda."}, ensure_ascii=False)
        query = query.strip()[:MAX_QUERY]
        try:
            if name == INVENTORY_TOOL.name and self._catalog is not None:
                return await self._inventory(query)
            if name == EQUIPMENT_TOOL.name and self._clients is not None:
                return await self._equipment(query)
        except Exception:  # noqa: BLE001 - un fallo de herramienta no debe tumbar la respuesta
            return json.dumps({"error": "La consulta falló; dilo al técnico en lugar de inventar datos."},
                              ensure_ascii=False)
        return json.dumps({"error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)

    async def _inventory(self, query: str) -> str:
        products = await self._catalog.list_products(query=None, category=None,
                                                     include_inactive=False, low_stock_only=False)
        found = rank_products(products, query)
        return json.dumps({
            "busqueda": query,
            "resultados": [{
                "codigo": p["sku"], "nombre": p["name"],
                "marca_modelo": " ".join(filter(None, [p.get("brand"), p.get("model")])) or None,
                "total_disponible": p["total_quantity"], "unidad": p["unit"],
                "bajo_stock": p["is_low_stock"],
                "por_ubicacion": {s["location_name"]: s["quantity"] for s in p["stock"]},
            } for p in found],
            "nota": None if found else "No hay productos que coincidan en el inventario.",
        }, ensure_ascii=False)

    async def _equipment(self, query: str) -> str:
        matches = await self._clients.search_equipment(query, limit=3)
        results = []
        for item in matches:
            detail = await self._clients.get_equipment(str(item["id"])) or {}
            results.append({
                "cliente": item["client_name"],
                "equipo": " ".join(filter(None, [item["equipment_type"], item.get("brand"), item.get("model")])),
                "serial": item.get("serial_number"), "ubicacion": item.get("site_description"),
                "estado": item["status"],
                "reparaciones": [{
                    "fecha": r["opened_at"].date().isoformat() if hasattr(r["opened_at"], "date") else str(r["opened_at"]),
                    "estado": r["status"], "falla": r["problem_description"],
                    "diagnostico": r.get("diagnosis"), "solucion": r.get("solution"),
                } for r in (detail.get("repairs") or [])[:5]],
            })
        return json.dumps({"busqueda": query, "equipos": results,
                           "nota": None if results else "No se encontraron equipos con esos datos."},
                          ensure_ascii=False)
