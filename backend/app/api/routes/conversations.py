import base64
import binascii
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import Settings
from app.dependencies.auth import bearer_scheme, get_current_user
from app.repositories.conversations import (
    ConversationStoreError,
    ConversationStoreUnavailable,
    SupabaseConversationRepository,
)
from app.schemas.conversations import (
    ConversationCreate,
    ConversationList,
    ConversationSummary,
    MessageCreate,
    MessageList,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _repository(request: Request, credentials: HTTPAuthorizationCredentials | None):
    factory = getattr(request.app.state, "conversation_repository_factory", None)
    if factory:
        return factory(credentials.credentials if credentials else "")
    settings: Settings = request.app.state.settings
    return SupabaseConversationRepository(settings, credentials.credentials if credentials else "")


def _owner_id(user: dict) -> str:
    try:
        return str(UUID(user["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, "Authentication required") from exc


def _cursor_offset(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        encoded = cursor.encode("ascii")
        decoded = base64.b64decode(encoded + b"=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        offset = int(decoded.decode("ascii"))
        if offset < 0 or offset > 10_000_000:
            raise ValueError("offset out of range")
        return offset
    except (ValueError, UnicodeDecodeError, UnicodeEncodeError, binascii.Error):
        raise HTTPException(400, "Invalid cursor")


def _next_cursor(offset: int, limit: int, row_count: int) -> str | None:
    if row_count <= limit:
        return None
    next_offset = str(offset + limit).encode("ascii")
    return base64.urlsafe_b64encode(next_offset).decode("ascii").rstrip("=")


async def _store_call(operation):
    try:
        return await operation
    except ConversationStoreUnavailable as exc:
        raise HTTPException(503, "Conversation storage is temporarily unavailable") from exc
    except ConversationStoreError as exc:
        raise HTTPException(500, "Could not persist conversation data") from exc


async def _owned_conversation(repository, owner_user_id: str, conversation_id: UUID):
    conversation = await _store_call(repository.get_conversation(owner_user_id, str(conversation_id)))
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return conversation


@router.post("", response_model=ConversationSummary, status_code=201)
async def create_conversation(
    request: Request,
    payload: ConversationCreate | None = None,
    user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    owner = _owner_id(user)
    repository = _repository(request, credentials)
    row = await _store_call(repository.create_conversation(
        owner, (payload.title if payload else None) or "Nueva conversación"
    ))
    return ConversationSummary.model_validate(row)


@router.get("", response_model=ConversationList)
async def list_conversations(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=32),
    user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    owner = _owner_id(user)
    repository = _repository(request, credentials)
    offset = _cursor_offset(cursor)
    rows = await _store_call(repository.list_conversations(owner, limit + 1, offset))
    next_cursor = _next_cursor(offset, limit, len(rows))
    return ConversationList(items=[ConversationSummary.model_validate(row) for row in rows[:limit]], next_cursor=next_cursor)


@router.get("/{conversation_id}", response_model=ConversationSummary)
async def get_conversation(
    conversation_id: UUID,
    request: Request,
    user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    repository = _repository(request, credentials)
    return ConversationSummary.model_validate(
        await _owned_conversation(repository, _owner_id(user), conversation_id)
    )


@router.get("/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    conversation_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=32),
    user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    owner = _owner_id(user)
    repository = _repository(request, credentials)
    await _owned_conversation(repository, owner, conversation_id)
    offset = _cursor_offset(cursor)
    rows = await _store_call(repository.list_messages(owner, str(conversation_id), limit + 1, offset))
    next_cursor = _next_cursor(offset, limit, len(rows))
    return MessageList(items=[MessageResponse.model_validate(row) for row in rows[:limit]], next_cursor=next_cursor)


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def create_message(
    conversation_id: UUID,
    payload: MessageCreate,
    request: Request,
    user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    owner = _owner_id(user)
    repository = _repository(request, credentials)
    await _owned_conversation(repository, owner, conversation_id)
    row = await _store_call(repository.create_message(owner, str(conversation_id), payload.content_text))
    return MessageResponse.model_validate(row)
