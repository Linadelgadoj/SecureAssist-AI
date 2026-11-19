"""Cursores opacos de paginación (offset codificado en base64 url-safe)."""
from __future__ import annotations

import base64
import binascii

from fastapi import HTTPException

MAX_OFFSET = 10_000_000


def decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        encoded = cursor.encode("ascii")
        decoded = base64.b64decode(encoded + b"=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        offset = int(decoded.decode("ascii"))
        if offset < 0 or offset > MAX_OFFSET:
            raise ValueError("offset out of range")
        return offset
    except (ValueError, UnicodeDecodeError, UnicodeEncodeError, binascii.Error):
        raise HTTPException(400, "Invalid cursor")


def encode_next_cursor(offset: int, limit: int, has_more: bool) -> str | None:
    if not has_more:
        return None
    return base64.urlsafe_b64encode(str(offset + limit).encode("ascii")).decode("ascii").rstrip("=")
