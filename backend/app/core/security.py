from __future__ import annotations

from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError, PyJWTError


class TokenValidationError(Exception):
    pass


class TokenVerificationUnavailable(TokenValidationError):
    pass


class SupabaseJWTVerifier:
    def __init__(self, jwks_url: str, issuer: str):
        self.issuer = issuer
        self.jwks = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300, max_cached_keys=16, timeout=5)

    def verify(self, token: str) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in {"ES256", "RS256"} or not header.get("kid"):
                raise TokenValidationError("Unsupported JWT signing key")
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["ES256", "RS256"],
                issuer=self.issuer,
                audience="authenticated",
                options={"require": ["exp", "iss", "aud", "sub"]},
                leeway=0,
            )
            if not isinstance(claims.get("sub"), str):
                raise TokenValidationError("Invalid subject")
            UUID(claims["sub"])
            return claims
        except PyJWKClientConnectionError as exc:
            raise TokenVerificationUnavailable("JWKS is unavailable") from exc
        except (PyJWTError, PyJWKClientError, ValueError, KeyError) as exc:
            raise TokenValidationError("JWT validation failed") from exc

