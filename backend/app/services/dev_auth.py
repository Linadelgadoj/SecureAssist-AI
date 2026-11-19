"""Login de prueba SOLO para desarrollo local (DEV_LOGIN=true con APP_ENV=development).

Sustituye a Supabase/Google con un usuario fijo para poder probar la interfaz sin
credenciales reales. Recorre las mismas rutas /auth/* (state de un solo uso, cookie
HttpOnly de refresh, rotación) pero los tokens son aleatorios y viven en memoria del
proceso: se pierden al reiniciar el backend. Nunca se activa en producción.
"""
from __future__ import annotations

import hmac
import secrets
from types import SimpleNamespace
from urllib.parse import urlencode

from app.core.config import Settings
from app.core.security import TokenValidationError
from app.schemas.auth import AuthUser
from app.services.auth_service import AuthRejected

DEV_USER = AuthUser(
    id="00000000-0000-4000-8000-000000000001",
    email="dev@localhost",
    email_verified=True,
    name="Usuario de prueba",
)
# Segundo usuario para probar el rol técnico (login_hint=tecnico@localhost).
DEV_TECHNICIAN = AuthUser(
    id="00000000-0000-4000-8000-000000000002",
    email="tecnico@localhost",
    email_verified=True,
    name="Técnico de prueba",
)
DEV_USERS = {user.email: user for user in (DEV_USER, DEV_TECHNICIAN)}
DEV_TOKEN_SECONDS = 3600


class _DevVerifier:
    def __init__(self, access_tokens: dict[str, AuthUser]):
        self._access_tokens = access_tokens

    def verify(self, token: str) -> dict:
        user = self._access_tokens.get(token)
        if user is None:
            raise TokenValidationError("invalid dev token")
        return {"sub": user.id, "email": user.email, "name": user.name}


class DevAuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._states: set[str] = set()
        self._access: dict[str, AuthUser] = {}
        self._refresh: dict[str, AuthUser] = {}
        self.verifier = _DevVerifier(self._access)

    def start(self, login_hint: str | None = None) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        self._states.add(state)
        user = DEV_USERS.get((login_hint or "").lower(), DEV_USER)
        query = urlencode({"code": f"dev:{user.email}", "state": state})
        return state, f"{self.settings.supabase_auth_callback_url}?{query}"

    def consume_state(self, provided_state: str, cookie_state: str | None):
        if not cookie_state or not hmac.compare_digest(provided_state, cookie_state) or provided_state not in self._states:
            raise AuthRejected()
        self._states.discard(provided_state)
        return SimpleNamespace(code_verifier="dev")

    async def exchange_and_validate(self, code: str, verifier: str) -> tuple[str, str, AuthUser, int]:
        return self._issue(DEV_USERS.get(code.removeprefix("dev:"), DEV_USER))

    async def renew(self, refresh_token: str) -> tuple[str, str, AuthUser, int]:
        user = self._refresh.pop(refresh_token, None)
        if user is None:
            raise AuthRejected()
        return self._issue(user)

    async def logout(self, refresh_token: str | None) -> None:
        if refresh_token:
            self._refresh.pop(refresh_token, None)

    async def aclose(self) -> None:
        return None

    def _issue(self, user: AuthUser) -> tuple[str, str, AuthUser, int]:
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self._access[access] = user
        self._refresh[refresh] = user
        return access, refresh, user, DEV_TOKEN_SECONDS
