"""Errores del dominio, independientes de HTTP y del almacenamiento concreto.

La capa de presentación los traduce a respuestas HTTP en `app.core.errors`.
"""


class DomainError(Exception):
    """Base de los errores que los casos de uso comunican a la presentación."""


class NotFoundError(DomainError):
    """El recurso no existe o no pertenece a quien lo pide (no se distingue a propósito)."""


class StorageError(DomainError):
    """El almacenamiento rechazó la operación."""


class StorageUnavailable(StorageError):
    """El almacenamiento no está disponible temporalmente."""
