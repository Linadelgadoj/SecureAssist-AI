from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


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
        code_by_status = {
            400: "INVALID_REQUEST",
            401: "AUTH_REQUIRED",
            403: "FORBIDDEN",
            404: "RESOURCE_NOT_FOUND",
            409: "CONFLICT",
            413: "FILE_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
            429: "RATE_LIMITED",
            502: "UPSTREAM_ERROR",
            503: "SERVICE_UNAVAILABLE",
            504: "UPSTREAM_TIMEOUT",
        }
        message_by_status = {
            400: "La solicitud no es válida.",
            401: "Debes iniciar sesión para continuar.",
            403: "No tienes permiso para realizar esta acción.",
            404: "No se encontró el recurso solicitado.",
            409: "La solicitud entra en conflicto con el estado actual.",
            413: "El archivo supera el tamaño permitido.",
            415: "El formato enviado no está permitido.",
            429: "Se alcanzó el límite de solicitudes. Intenta más tarde.",
            502: "Un servicio externo no pudo completar la solicitud.",
            503: "El servicio no está disponible temporalmente.",
            504: "El servicio externo tardó demasiado. Intenta nuevamente.",
        }
        status = exc.status_code
        # Never echo exception details that could expose internal state.
        return _error_response(
            request,
            status,
            code_by_status.get(status, "REQUEST_FAILED"),
            message_by_status.get(status, "No fue posible procesar la solicitud."),
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        return _error_response(
            request,
            500,
            "INTERNAL_ERROR",
            "Ocurrió un error interno. Intenta nuevamente más tarde.",
        )
