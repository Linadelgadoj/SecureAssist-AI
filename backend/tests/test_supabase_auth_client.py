import asyncio

import httpx
import pytest

from app.services.supabase_auth_client import SupabaseAuthClient, SupabaseAuthError


def test_auth_client_uses_official_pkce_token_contract_and_publishable_key():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 3600})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseAuthClient("https://sample.supabase.co/auth/v1", "publishable-only", http)
    result = asyncio.run(client.exchange_code("one-time-code", "pkce-verifier"))
    request = seen[0]
    assert request.url.path == "/auth/v1/token"
    assert request.url.params["grant_type"] == "pkce"
    assert request.headers["apikey"] == "publishable-only"
    assert "authorization" not in request.headers
    assert request.content == b'{"auth_code":"one-time-code","code_verifier":"pkce-verifier"}'
    assert result["refresh_token"] == "r"
    asyncio.run(http.aclose())


def test_auth_client_normalizes_provider_errors_without_returning_details():
    def handler(_request):
        return httpx.Response(401, json={"msg": "private provider response"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SupabaseAuthClient("https://sample.supabase.co/auth/v1", "publishable-only", http)
    with pytest.raises(SupabaseAuthError) as error:
        asyncio.run(client.refresh("bad-refresh"))
    assert error.value.status == 401
    assert "private provider response" not in str(error.value)
    asyncio.run(http.aclose())
