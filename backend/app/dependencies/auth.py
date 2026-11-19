from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import TokenValidationError, TokenVerificationUnavailable
from app.dependencies.services import bearer_scheme, get_auth_provider

__all__ = ["bearer_scheme", "get_current_user", "get_current_user_id"]


def _unauthorized() -> HTTPException:
    return HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    provider = get_auth_provider(request, require_configuration=True)
    try:
        return provider.verifier.verify(credentials.credentials)
    except TokenVerificationUnavailable as exc:
        raise HTTPException(503, "Authentication keys are temporarily unavailable") from exc
    except TokenValidationError as exc:
        raise _unauthorized() from exc


async def get_current_user_id(user: dict = Depends(get_current_user)) -> str:
    """UUID normalizado del usuario autenticado (claim `sub`)."""
    try:
        return str(UUID(user["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise _unauthorized() from exc
