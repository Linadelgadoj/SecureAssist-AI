from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.application.users import UserService, require_admin
from app.core.security import TokenValidationError, TokenVerificationUnavailable
from app.dependencies.services import bearer_scheme, get_auth_provider, get_user_service
from app.domain.users import AppUser

__all__ = ["bearer_scheme", "get_current_account", "get_current_admin", "get_current_user", "get_current_user_id"]


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


async def get_current_account(
    user: dict = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
) -> AppUser:
    """Usuario de la aplicación (con rol). Lo registra como técnico la primera vez."""
    await get_current_user_id(user)  # valida que `sub` sea un UUID
    return await users.resolve(user)


async def get_current_admin(account: AppUser = Depends(get_current_account)) -> AppUser:
    require_admin(account)
    return account


async def get_current_account_id(account: AppUser = Depends(get_current_account)) -> str:
    return account.id
