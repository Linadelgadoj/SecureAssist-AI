import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value):
        return value.strip() if isinstance(value, str) else value


class ConversationSummary(BaseModel):
    id: UUID
    title: str
    state: Literal["open"]
    created_at: datetime
    last_activity_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    next_cursor: str | None = None


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_text: str = Field(min_length=1, max_length=8000)

    @field_validator("content_text", mode="before")
    @classmethod
    def normalize_content(cls, value):
        if not isinstance(value, str):
            return value
        content = value.strip()
        credential_patterns = (
            r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{16,}",
            r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
            r"(?i)\b(?:password|contrase(?:ñ|n)a)\s*[:=]\s*\S+",
        )
        if any(re.search(pattern, content) for pattern in credential_patterns):
            raise ValueError("No incluyas contraseñas ni tokens de autenticación en el mensaje.")
        return content


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: Literal["installer", "assistant"]
    content_text: str
    processing_state: Literal["received", "completed", "failed"]
    created_at: datetime


class MessageList(BaseModel):
    items: list[MessageResponse]
    next_cursor: str | None = None
