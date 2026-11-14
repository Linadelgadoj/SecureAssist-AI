from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass


class OAuthTransactionError(Exception):
    pass


@dataclass(frozen=True)
class OAuthTransaction:
    code_verifier: str
    expires_at: float


class OAuthTransactionStore:
    """Bounded single-process store; use a shared store before scaling workers."""

    def __init__(self, ttl_seconds: int = 600, max_entries: int = 1024):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, OAuthTransaction] = {}
        self._lock = threading.Lock()

    def create(self, code_verifier: str) -> tuple[str, OAuthTransaction]:
        now = time.time()
        with self._lock:
            self._purge(now)
            if len(self._entries) >= self.max_entries:
                raise OAuthTransactionError("OAuth temporal storage is full")
            state = secrets.token_urlsafe(32)
            transaction = OAuthTransaction(code_verifier, now + self.ttl_seconds)
            self._entries[state] = transaction
            return state, transaction

    def consume(self, state: str) -> OAuthTransaction:
        now = time.time()
        with self._lock:
            transaction = self._entries.pop(state, None)
            self._purge(now)
        if transaction is None or transaction.expires_at <= now:
            raise OAuthTransactionError("OAuth transaction is invalid or expired")
        return transaction

    def _purge(self, now: float) -> None:
        expired = [key for key, item in self._entries.items() if item.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)

