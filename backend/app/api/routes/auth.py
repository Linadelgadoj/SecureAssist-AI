from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.config import Settings
from app.dependencies.services import get_auth_provider
from app.domain.ports import AuthProvider
from app.repositories.oauth_transactions import OAuthTransactionError
from app.schemas.auth import SessionResponse
from app.services.auth_service import AuthRejected, AuthUnavailable

router = APIRouter(prefix="/auth", tags=["auth"])
STATE_COOKIE = "secureassist_oauth_state"


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _service(request: Request) -> AuthProvider:
    return get_auth_provider(request)


def _set_refresh_cookie(response: Response, settings: Settings, token: str) -> None:
    kwargs = dict(key=settings.auth_cookie_name, value=token, httponly=True, secure=settings.auth_cookie_secure,
                  samesite="lax", path="/api/v1/auth", domain=settings.auth_cookie_domain)
    if settings.auth_cookie_max_age_seconds:
        kwargs["max_age"] = settings.auth_cookie_max_age_seconds
    response.set_cookie(**kwargs)


def _clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.auth_cookie_name, path="/api/v1/auth", domain=settings.auth_cookie_domain,
                           secure=settings.auth_cookie_secure, httponly=True, samesite="lax")


def _clear_state_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(STATE_COOKIE, path="/api/v1/auth/google/callback", secure=settings.auth_cookie_secure,
                           httponly=True, samesite="lax")


def _auth_failed_redirect(settings: Settings) -> RedirectResponse:
    response = RedirectResponse(
        f"{settings.frontend_auth_success_url}?{urlencode({'auth_error': 'authentication_failed'})}", status_code=303
    )
    _clear_state_cookie(response, settings)
    return response


def _session_error(request: Request, settings: Settings, status: int, code: str, message: str) -> JSONResponse:
    result = JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "details": [], "request_id": request.state.request_id,
    }})
    _clear_cookie(result, settings)
    return result


def _require_origin(request: Request, settings: Settings) -> None:
    if request.headers.get("origin") != settings.frontend_origin:
        raise HTTPException(status_code=403, detail="Invalid origin")


@router.get("/google/start")
async def google_start(request: Request):
    try:
        state, url = _service(request).start()
    except (ValueError, OAuthTransactionError):
        raise HTTPException(503, "Authentication is not configured")
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(STATE_COOKIE, state, httponly=True, secure=_settings(request).auth_cookie_secure,
                        samesite="lax", path="/api/v1/auth/google/callback", max_age=600)
    return response


@router.get("/google/callback")
async def google_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    settings = _settings(request)
    service = _service(request)
    if error or not code or not state:
        if error and state:
            try:
                service.consume_state(state, request.cookies.get(STATE_COOKIE))
            except (OAuthTransactionError, AuthRejected):
                pass
        return _auth_failed_redirect(settings)
    try:
        transaction = service.consume_state(state, request.cookies.get(STATE_COOKIE))
        access, refresh, user, expires = await service.exchange_and_validate(code, transaction.code_verifier)
    except (OAuthTransactionError, AuthRejected):
        return _auth_failed_redirect(settings)
    except AuthUnavailable:
        raise HTTPException(503, "Authentication provider is temporarily unavailable")
    response = RedirectResponse(settings.frontend_auth_success_url, status_code=303)
    _set_refresh_cookie(response, settings, refresh)
    _clear_state_cookie(response, settings)
    return response


def _session_payload(access: str, user, expires: int) -> SessionResponse:
    return SessionResponse(authenticated=True, user=user, access_token=access, token_type="bearer", expires_in=expires)


@router.get("/session", response_model=SessionResponse)
async def session(request: Request, response: Response):
    settings = _settings(request)
    _require_origin(request, settings)
    refresh = request.cookies.get(settings.auth_cookie_name)
    if not refresh:
        return SessionResponse(authenticated=False)
    try:
        access, rotated, user, expires = await _service(request).renew(refresh)
    except AuthRejected:
        _clear_cookie(response, settings)
        return SessionResponse(authenticated=False)
    except AuthUnavailable:
        raise HTTPException(503, "Authentication provider is temporarily unavailable")
    _set_refresh_cookie(response, settings, rotated)
    return _session_payload(access, user, expires)


@router.post("/refresh", response_model=SessionResponse)
async def refresh_session(request: Request, response: Response):
    settings = _settings(request)
    _require_origin(request, settings)
    refresh = request.cookies.get(settings.auth_cookie_name)
    if not refresh:
        raise HTTPException(401, "Session is not valid")
    try:
        access, rotated, user, expires = await _service(request).renew(refresh)
    except AuthRejected:
        return _session_error(request, settings, 401, "AUTH_INVALID", "La sesión no es válida. Inicia sesión nuevamente.")
    except AuthUnavailable:
        raise HTTPException(503, "Authentication provider is temporarily unavailable")
    _set_refresh_cookie(response, settings, rotated)
    return _session_payload(access, user, expires)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    settings = _settings(request)
    _require_origin(request, settings)
    await _service(request).logout(request.cookies.get(settings.auth_cookie_name))
    _clear_cookie(response, settings)
    response.status_code = 204
    return response

