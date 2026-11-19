from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.assistant import AssistantUnavailable
from app.domain.errors import ConflictError, ForbiddenError, NotFoundError, StorageError, StorageUnavailable

CODE_BY_STATUS = {
    400: "INVALID_REQUEST",
    401: "AUTH_REQUIRED",
    403: "FORBIDDEN",
    404: "RESOURCE_NOT_FOUND",
    409: "CONFLICT",
    413: "FILE_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
    504: "UPSTREAM_TIMEOUT",
}
MESSAGE_BY_STATUS = {
    400: "La solicitud no es válida.",
    401: "Debes iniciar sesión para continuar.",
    403: "No tienes permiso para realizar esta acción.",
    404: "No se encontró el recurso solicitado.",
    409: "La solicitud entra en conflicto con el estado actual.",
    413: "El archivo supera el tamaño permitido.",
    415: "El formato enviado no está permitido.",
    429: "Se alcanzó el límite de solicitudes. Intenta más tarde.",
    500: "Ocurrió un error interno. Intenta nuevamente más tarde.",
    502: "Un servicio externo no pudo completar la solicitud.",
    503: "El servicio no está disponible temporalmente.",
    504: "El servicio externo tardó demasiado. Intenta nuevamente.",
}
# Errores de dominio -> estado HTTP. La búsqueda sigue el MRO, así que
# StorageUnavailable (503) gana sobre su clase base StorageError (500).
STATUS_BY_DOMAIN_ERROR = {NotFoundError: 404, ForbiddenError: 403, StorageUnavailable: 503, StorageError: 500}


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "request_id": request.state.request_id,
            }
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "reason": str(error.get("type", "invalid")),
            }
            for error in exc.errors()
        ]
        return _error_response(
            request, 422, "VALIDATION_ERROR", "Revisa los datos enviados.", details
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        status = exc.status_code
        # Never echo exception details that could expose internal state.
        return _error_response(
            request,
            status,
            CODE_BY_STATUS.get(status, "REQUEST_FAILED"),
            MESSAGE_BY_STATUS.get(status, "No fue posible procesar la solicitud."),
        )

    def _domain_handler(status: int):
        async def handler(request: Request, _exc: Exception) -> JSONResponse:
            return _error_response(request, status, CODE_BY_STATUS[status], MESSAGE_BY_STATUS[status])
        return handler

    for error_type, status in STATUS_BY_DOMAIN_ERROR.items():
        app.add_exception_handler(error_type, _domain_handler(status))

    @app.exception_handler(AssistantUnavailable)
    async def assistant_unavailable(request: Request, exc: AssistantUnavailable) -> JSONResponse:
        return _error_response(request, 503, "ASSISTANT_UNAVAILABLE", exc.message)

    @app.exception_handler(ConflictError)
    async def conflict_error(request: Request, exc: ConflictError) -> JSONResponse:
        # El mensaje de un conflicto es de negocio y está pensado para mostrarse al usuario.
        return _error_response(request, 409, exc.code, exc.message)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        return _error_response(
            request,
            500,
            "INTERNAL_ERROR",
            "Ocurrió un error interno. Intenta nuevamente más tarde.",
        )
