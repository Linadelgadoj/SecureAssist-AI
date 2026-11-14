import os
from dataclasses import dataclass
from urllib.parse import urlsplit


def _split_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str
    cors_origins: list[str]
    frontend_origin: str
    supabase_url: str
    supabase_publishable_key: str
    supabase_auth_callback_url: str
    frontend_auth_success_url: str
    auth_cookie_secure: bool
    auth_cookie_name: str
    auth_cookie_domain: str | None
    auth_cookie_max_age_seconds: int | None

    @property
    def supabase_auth_url(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_auth_url}/.well-known/jwks.json"

    @property
    def supabase_jwt_issuer(self) -> str:
        return self.supabase_auth_url

    def require_auth_configuration(self) -> None:
        required = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_PUBLISHABLE_KEY": self.supabase_publishable_key,
            "SUPABASE_AUTH_CALLBACK_URL": self.supabase_auth_callback_url,
            "FRONTEND_AUTH_SUCCESS_URL": self.frontend_auth_success_url,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError("Falta configuración del proveedor de identidad.")

        supabase = urlsplit(self.supabase_url)
        callback = urlsplit(self.supabase_auth_callback_url)
        success = urlsplit(self.frontend_auth_success_url)
        if supabase.scheme != "https" and supabase.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("SUPABASE_URL debe usar HTTPS fuera de desarrollo local.")
        if not supabase.netloc or supabase.query or supabase.fragment:
            raise ValueError("SUPABASE_URL no tiene un formato válido.")
        if callback.scheme not in {"http", "https"} or not callback.netloc:
            raise ValueError("La URL de callback no es válida.")
        if callback.query or callback.fragment:
            raise ValueError("SUPABASE_AUTH_CALLBACK_URL debe ser una URL base sin query ni fragmento.")
        if success.scheme not in {"http", "https"} or not success.netloc:
            raise ValueError("La URL de destino del frontend no es válida.")
        if f"{success.scheme}://{success.netloc}" != self.frontend_origin:
            raise ValueError("FRONTEND_AUTH_SUCCESS_URL debe pertenecer a FRONTEND_ORIGIN.")
        if self.app_env == "production":
            if callback.scheme != "https" or success.scheme != "https":
                raise ValueError("Las URL de autenticación deben usar HTTPS en producción.")
            if not self.auth_cookie_max_age_seconds:
                raise ValueError("AUTH_COOKIE_MAX_AGE_SECONDS debe alinearse con la sesión de Supabase en producción.")


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} debe ser true o false.")
    return value == "true"


def _read_optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{name} debe ser un entero positivo.")
    return value


def get_settings() -> Settings:
    """Read only server-safe settings from the process environment."""
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").rstrip("/")
    cors_origins = _split_origins(os.getenv("CORS_ORIGINS", frontend_origin))
    if "*" in cors_origins:
        raise ValueError("CORS_ORIGINS no puede usar wildcard.")
    if frontend_origin not in cors_origins:
        cors_origins.append(frontend_origin)
    cookie_secure = _read_bool("AUTH_COOKIE_SECURE", app_env == "production")
    if app_env == "production" and not cookie_secure:
        raise ValueError("AUTH_COOKIE_SECURE debe ser true en producción.")

    return Settings(
        app_env=app_env,
        cors_origins=cors_origins,
        frontend_origin=frontend_origin,
        supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip(),
        supabase_auth_callback_url=os.getenv("SUPABASE_AUTH_CALLBACK_URL", "").strip(),
        frontend_auth_success_url=os.getenv("FRONTEND_AUTH_SUCCESS_URL", "").strip(),
        auth_cookie_secure=cookie_secure,
        auth_cookie_name=os.getenv("AUTH_COOKIE_NAME", "secureassist_refresh").strip(),
        auth_cookie_domain=os.getenv("AUTH_COOKIE_DOMAIN", "").strip() or None,
        auth_cookie_max_age_seconds=_read_optional_positive_int("AUTH_COOKIE_MAX_AGE_SECONDS"),
    )
