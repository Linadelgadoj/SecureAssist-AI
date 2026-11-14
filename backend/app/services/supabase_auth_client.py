from __future__ import annotations

from urllib.parse import urlencode

import httpx


class SupabaseAuthError(Exception):
    def __init__(self, status: int | None = None):
        self.status = status
        super().__init__("Supabase Auth request failed")


class SupabaseAuthClient:
    def __init__(self, base_url: str, publishable_key: str, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.publishable_key = publishable_key
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=4.0))

    def authorization_url(self, redirect_to: str, challenge: str) -> str:
        query = urlencode({
            "provider": "google",
            "redirect_to": redirect_to,
            "code_challenge": challenge,
            "code_challenge_method": "s256",
        })
        return f"{self.base_url}/authorize?{query}"

    async def _post(self, path: str, body: dict, params: dict | None = None) -> dict:
        try:
            response = await self.client.post(
                f"{self.base_url}{path}", params=params,
                headers={"apikey": self.publishable_key, "Content-Type": "application/json"}, json=body,
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError() from exc
        if response.status_code >= 400:
            raise SupabaseAuthError(response.status_code)
        try:
            data = response.json()
        except ValueError as exc:
            raise SupabaseAuthError(response.status_code) from exc
        if not isinstance(data, dict):
            raise SupabaseAuthError(response.status_code)
        return data

    async def exchange_code(self, code: str, verifier: str) -> dict:
        return await self._post("/token", {"auth_code": code, "code_verifier": verifier}, {"grant_type": "pkce"})

    async def refresh(self, refresh_token: str) -> dict:
        return await self._post("/token", {"refresh_token": refresh_token}, {"grant_type": "refresh_token"})

    async def user(self, access_token: str) -> dict:
        try:
            response = await self.client.get(
                f"{self.base_url}/user",
                headers={"apikey": self.publishable_key, "Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError() from exc
        if response.status_code >= 400:
            raise SupabaseAuthError(response.status_code)
        try:
            data = response.json()
        except ValueError as exc:
            raise SupabaseAuthError(response.status_code) from exc
        if not isinstance(data, dict):
            raise SupabaseAuthError(response.status_code)
        return data

    async def logout(self, access_token: str) -> None:
        try:
            response = await self.client.post(
                f"{self.base_url}/logout", params={"scope": "local"},
                headers={"apikey": self.publishable_key, "Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError() from exc
        if response.status_code >= 400:
            raise SupabaseAuthError(response.status_code)

