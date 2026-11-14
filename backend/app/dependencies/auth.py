from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import TokenValidationError, TokenVerificationUnavailable
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    service = request.app.state.auth_service
    if service is None:
        try:
            request.app.state.settings.require_auth_configuration()
            service = AuthService(request.app.state.settings)
            request.app.state.auth_service = service
        except ValueError as exc:
            raise HTTPException(503, "Authentication is not configured") from exc
    try:
        return service.verifier.verify(credentials.credentials)
    except TokenVerificationUnavailable as exc:
        raise HTTPException(503, "Authentication keys are temporarily unavailable") from exc
    except TokenValidationError as exc:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}) from exc
