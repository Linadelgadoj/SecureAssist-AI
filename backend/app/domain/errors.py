"""Errores del dominio, independientes de HTTP y del almacenamiento concreto.

La capa de presentación los traduce a respuestas HTTP en `app.core.errors`.
"""


class DomainError(Exception):
    """Base de los errores que los casos de uso comunican a la presentación."""


class NotFoundError(DomainError):
    """El recurso no existe o no pertenece a quien lo pide (no se distingue a propósito)."""


class ForbiddenError(DomainError):
    """El usuario está autenticado pero su rol no permite la acción."""


class ConflictError(DomainError):
    """La operación choca con el estado actual (stock insuficiente, duplicado, último admin...)."""

    def __init__(self, message: str, code: str = "CONFLICT"):
        super().__init__(message)
        self.message = message
        self.code = code


class StorageError(DomainError):
    """El almacenamiento rechazó la operación."""


class StorageUnavailable(StorageError):
    """El almacenamiento no está disponible temporalmente."""
