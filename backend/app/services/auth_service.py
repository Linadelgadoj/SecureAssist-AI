from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from urllib.parse import urlencode

from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import SupabaseJWTVerifier, TokenValidationError, TokenVerificationUnavailable
from app.repositories.oauth_transactions import OAuthTransactionStore
from app.schemas.auth import AuthUser
from app.services.supabase_auth_client import SupabaseAuthClient, SupabaseAuthError


class AuthRejected(Exception):
    pass


class AuthUnavailable(Exception):
    pass


@contextmanager
def _translate_provider_errors():
    """Convierte fallos del proveedor en AuthRejected (credencial inválida) o AuthUnavailable."""
    try:
        yield
    except AuthRejected:
        raise
    except TokenVerificationUnavailable as exc:
        raise AuthUnavailable() from exc
    except TokenValidationError as exc:
        raise AuthRejected() from exc
    except SupabaseAuthError as exc:
        if exc.status in {400, 401, 403}:
            raise AuthRejected() from exc
        raise AuthUnavailable() from exc


class AuthService:
    def __init__(self, settings: Settings, client: SupabaseAuthClient | None = None, transactions: OAuthTransactionStore | None = None, verifier=None):
        self.settings = settings
        self.client = client or SupabaseAuthClient(settings.supabase_auth_url, settings.supabase_publishable_key)
        self.transactions = transactions or OAuthTransactionStore()
        self.verifier = verifier or SupabaseJWTVerifier(settings.supabase_jwks_url, settings.supabase_jwt_issuer)

    def start(self) -> tuple[str, str]:
        self.settings.require_auth_configuration()
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state, _ = self.transactions.create(verifier)
        separator = "&" if "?" in self.settings.supabase_auth_callback_url else "?"
        redirect_to = f"{self.settings.supabase_auth_callback_url}{separator}{urlencode({'state': state})}"
        return state, self.client.authorization_url(redirect_to, challenge)

    def consume_state(self, provided_state: str, cookie_state: str | None):
        if not cookie_state or not hmac.compare_digest(provided_state, cookie_state):
            raise AuthRejected()
        return self.transactions.consume(provided_state)

    async def exchange_and_validate(self, code: str, verifier: str) -> tuple[str, str, AuthUser, int]:
        with _translate_provider_errors():
            session = await self.client.exchange_code(code, verifier)
            access, refresh, expires = self._session_tokens(session)
            self.verifier.verify(access)
            user_data = await self.client.user(access)
            user = self._validate_user(user_data)
            session_user = session.get("user")
            if not isinstance(session_user, dict) or user.id != session_user.get("id"):
                raise AuthRejected()
            return access, refresh, user, expires

    async def renew(self, refresh_token: str) -> tuple[str, str, AuthUser, int]:
        with _translate_provider_errors():
            session = await self.client.refresh(refresh_token)
            access, refresh, expires = self._session_tokens(session)
            self.verifier.verify(access)
            user = self._validate_user(session.get("user") or await self.client.user(access))
            return access, refresh, user, expires

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        try:
            access, _, _, _ = await self.renew(refresh_token)
            await self.client.logout(access)
        except (AuthRejected, AuthUnavailable, SupabaseAuthError):
            # Local logout is unconditional; provider revocation is best-effort.
            return

    async def aclose(self) -> None:
        await self.client.aclose()

    @staticmethod
    def _session_tokens(session: dict) -> tuple[str, str, int]:
        access, refresh = session.get("access_token"), session.get("refresh_token")
        expires = session.get("expires_in")
        if (not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh
                or not isinstance(expires, int) or isinstance(expires, bool) or expires <= 0
                or (session.get("user") is not None and not isinstance(session.get("user"), dict))):
            raise AuthRejected()
        return access, refresh, expires

    @staticmethod
    def _validate_user(data: dict) -> AuthUser:
        if not isinstance(data, dict):
            raise AuthRejected()
        user_id, email = data.get("id"), data.get("email")
        confirmed = data.get("email_confirmed_at")
        metadata = data.get("app_metadata") or {}
        identities = data.get("identities") or []
        if not isinstance(metadata, dict) or not isinstance(identities, list):
            raise AuthRejected()
        providers = metadata.get("providers") or []
        if not isinstance(providers, list):
            raise AuthRejected()
        google_identity = metadata.get("provider") == "google" or "google" in providers or any(
            isinstance(identity, dict) and identity.get("provider") == "google" for identity in identities
        )
        if not isinstance(user_id, str) or not isinstance(email, str) or not email or not confirmed or not google_identity:
            raise AuthRejected()
        info = data.get("user_metadata") or {}
        if not isinstance(info, dict):
            raise AuthRejected()
        name = info.get("full_name") or info.get("name")
        picture = info.get("avatar_url") or info.get("picture")
        try:
            return AuthUser(id=user_id, email=email, email_verified=True,
                            name=name if isinstance(name, str) else None,
                            picture=picture if isinstance(picture, str) else None)
        except ValidationError as exc:
            raise AuthRejected() from exc

