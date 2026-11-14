from __future__ import annotations

import time
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError

from app.core.security import SupabaseJWTVerifier, TokenValidationError
from app.repositories.oauth_transactions import OAuthTransactionError, OAuthTransactionStore
from app.services.auth_service import AuthRejected, AuthService
from app.core.config import Settings


def make_settings(**changes) -> Settings:
    values = dict(
        app_env="development", cors_origins=["http://localhost:5173"], frontend_origin="http://localhost:5173",
        supabase_url="https://sample.supabase.co", supabase_publishable_key="publishable-test",
        supabase_auth_callback_url="http://localhost:8000/api/v1/auth/google/callback",
        frontend_auth_success_url="http://localhost:5173/", auth_cookie_secure=False,
        auth_cookie_name="secureassist_refresh", auth_cookie_domain=None, auth_cookie_max_age_seconds=None,
    )
    values.update(changes)
    return Settings(**values)


def test_oauth_transaction_is_consumed_only_once():
    store = OAuthTransactionStore(ttl_seconds=30)
    state, transaction = store.create("test-verifier")
    assert transaction.code_verifier == "test-verifier"
    assert store.consume(state) == transaction
    with pytest.raises(OAuthTransactionError):
        store.consume(state)


def test_oauth_transaction_expires(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.repositories.oauth_transactions.time.time", lambda: now[0])
    store = OAuthTransactionStore(ttl_seconds=5)
    state, _ = store.create("v")
    now[0] = 106.0
    with pytest.raises(OAuthTransactionError):
        store.consume(state)


def test_google_start_uses_supabase_pkce_authorize_endpoint():
    service = AuthService(make_settings(), transactions=OAuthTransactionStore())
    state, url = service.start()
    from urllib.parse import parse_qs, urlsplit
    query = parse_qs(urlsplit(url).query)
    assert state
    assert urlsplit(url).path.endswith("/authorize")
    assert query["provider"] == ["google"]
    assert query["code_challenge_method"] == ["s256"]
    assert len(query["code_challenge"][0]) == 43
    assert f"state={state}" in query["redirect_to"][0]


def test_state_requires_matching_browser_cookie():
    service = AuthService(make_settings(), transactions=OAuthTransactionStore())
    state, _ = service.start()
    with pytest.raises(AuthRejected):
        service.consume_state(state, "different")
    assert service.consume_state(state, state).code_verifier


def test_google_identity_requires_verified_email_and_google_provider():
    data = {
        "id": str(uuid4()), "email": "installer@example.com", "email_confirmed_at": "2026-01-01T00:00:00Z",
        "app_metadata": {"provider": "google"}, "identities": [], "user_metadata": {"full_name": "Installer"},
    }
    assert AuthService._validate_user(data).email_verified is True
    data["email_confirmed_at"] = None
    with pytest.raises(AuthRejected):
        AuthService._validate_user(data)
    data["email_confirmed_at"] = "now"
    data["app_metadata"] = {"provider": "email"}
    with pytest.raises(AuthRejected):
        AuthService._validate_user(data)


class FixedKeyClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, _token):
        if self.key is None:
            raise PyJWKClientError("missing key")
        return type("SigningKey", (), {"key": self.key})()


@pytest.fixture
def signing_keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def make_jwt(private, **overrides):
    claims = {
        "iss": "https://sample.supabase.co/auth/v1", "aud": "authenticated", "sub": str(uuid4()),
        "exp": int(time.time()) + 120, "iat": int(time.time()),
    }
    claims.update(overrides)
    return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "key-1"})


def test_jwt_verifier_checks_signature_claims_and_subject(signing_keys):
    private, public = signing_keys
    verifier = SupabaseJWTVerifier("https://sample.supabase.co/auth/v1/.well-known/jwks.json", "https://sample.supabase.co/auth/v1")
    verifier.jwks = FixedKeyClient(public)
    assert verifier.verify(make_jwt(private))["aud"] == "authenticated"
    with pytest.raises(TokenValidationError):
        verifier.verify(make_jwt(private, aud="other"))
    with pytest.raises(TokenValidationError):
        verifier.verify(make_jwt(private, iss="https://attacker.invalid"))
    with pytest.raises(TokenValidationError):
        verifier.verify(make_jwt(private, exp=int(time.time()) - 10))
    with pytest.raises(TokenValidationError):
        verifier.verify(make_jwt(private, sub="not-a-uuid"))


def test_jwt_bad_signature_and_unavailable_jwks_fail_closed(signing_keys):
    private, public = signing_keys
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = SupabaseJWTVerifier("https://sample.supabase.co/auth/v1/.well-known/jwks.json", "https://sample.supabase.co/auth/v1")
    verifier.jwks = FixedKeyClient(public)
    with pytest.raises(TokenValidationError):
        verifier.verify(make_jwt(other))
    verifier.jwks = FixedKeyClient(None)
    with pytest.raises(TokenValidationError):
        verifier.verify(make_jwt(private))


def test_jwt_rejects_symmetric_algorithms_and_missing_claims(signing_keys):
    private, public = signing_keys
    verifier = SupabaseJWTVerifier("https://sample.supabase.co/auth/v1/.well-known/jwks.json", "https://sample.supabase.co/auth/v1")
    verifier.jwks = FixedKeyClient(public)
    symmetric = jwt.encode({"sub": str(uuid4()), "iss": verifier.issuer, "aud": "authenticated", "exp": int(time.time()) + 60}, "not-a-server-key", algorithm="HS256", headers={"kid": "key-1"})
    with pytest.raises(TokenValidationError):
        verifier.verify(symmetric)
    missing_sub = jwt.encode({"iss": verifier.issuer, "aud": "authenticated", "exp": int(time.time()) + 60}, private, algorithm="RS256", headers={"kid": "key-1"})
    with pytest.raises(TokenValidationError):
        verifier.verify(missing_sub)


def test_jwks_network_failure_is_distinguished_from_invalid_token(signing_keys):
    from app.core.security import TokenVerificationUnavailable

    private, _ = signing_keys
    verifier = SupabaseJWTVerifier("https://sample.supabase.co/auth/v1/.well-known/jwks.json", "https://sample.supabase.co/auth/v1")

    class UnavailableKeyClient:
        def get_signing_key_from_jwt(self, _token):
            raise PyJWKClientConnectionError("offline")

    verifier.jwks = UnavailableKeyClient()
    with pytest.raises(TokenVerificationUnavailable):
        verifier.verify(make_jwt(private))

