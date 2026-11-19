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
DEV_TOKEN_SECONDS = 3600


class _DevVerifier:
    def __init__(self, access_tokens: set[str]):
        self._access_tokens = access_tokens

    def verify(self, token: str) -> dict:
        if token not in self._access_tokens:
            raise TokenValidationError("invalid dev token")
        return {"sub": DEV_USER.id, "email": DEV_USER.email}


class DevAuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._states: set[str] = set()
        self._access: set[str] = set()
        self._refresh: set[str] = set()
        self.verifier = _DevVerifier(self._access)

    def start(self) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        self._states.add(state)
        return state, f"{self.settings.supabase_auth_callback_url}?{urlencode({'code': 'dev', 'state': state})}"

    def consume_state(self, provided_state: str, cookie_state: str | None):
        if not cookie_state or not hmac.compare_digest(provided_state, cookie_state) or provided_state not in self._states:
            raise AuthRejected()
        self._states.discard(provided_state)
        return SimpleNamespace(code_verifier="dev")

    async def exchange_and_validate(self, code: str, verifier: str) -> tuple[str, str, AuthUser, int]:
        return self._issue()

    async def renew(self, refresh_token: str) -> tuple[str, str, AuthUser, int]:
        if refresh_token not in self._refresh:
            raise AuthRejected()
        self._refresh.discard(refresh_token)
        return self._issue()

    async def logout(self, refresh_token: str | None) -> None:
        if refresh_token:
            self._refresh.discard(refresh_token)

    async def aclose(self) -> None:
        return None

    def _issue(self) -> tuple[str, str, AuthUser, int]:
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self._access.add(access)
        self._refresh.add(refresh)
        return access, refresh, DEV_USER, DEV_TOKEN_SECONDS
