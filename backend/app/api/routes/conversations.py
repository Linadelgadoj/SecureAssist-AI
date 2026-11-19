"""Rutas HTTP del historial. Solo traducen HTTP <-> casos de uso de ConversationService.

Los errores de dominio (NotFoundError, StorageError, StorageUnavailable) los
convierte en respuestas uniformes `app.core.errors`.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.pagination import decode_cursor, encode_next_cursor
from app.application.conversations import ConversationService
from app.dependencies.auth import get_current_user_id
from app.dependencies.services import get_conversation_service
from app.schemas.conversations import (
    ConversationCreate,
    ConversationList,
    ConversationSummary,
    MessageCreate,
    MessageList,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationSummary, status_code=201)
async def create_conversation(
    payload: ConversationCreate | None = None,
    owner: str = Depends(get_current_user_id),
    service: ConversationService = Depends(get_conversation_service),
):
    row = await service.start_conversation(owner, payload.title if payload else None)
    return ConversationSummary.model_validate(row)


@router.get("", response_model=ConversationList)
async def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=32),
    owner: str = Depends(get_current_user_id),
    service: ConversationService = Depends(get_conversation_service),
):
    offset = decode_cursor(cursor)
    page = await service.list_conversations(owner, limit, offset)
    return ConversationList(
        items=[ConversationSummary.model_validate(row) for row in page.items],
        next_cursor=encode_next_cursor(offset, limit, page.has_more),
    )


@router.get("/{conversation_id}", response_model=ConversationSummary)
async def get_conversation(
    conversation_id: UUID,
    owner: str = Depends(get_current_user_id),
    service: ConversationService = Depends(get_conversation_service),
):
    return ConversationSummary.model_validate(await service.get_conversation(owner, str(conversation_id)))


@router.get("/{conversation_id}/messages", response_model=MessageList)
async def list_messages(
    conversation_id: UUID,
    limit: int = Query(default=100, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=32),
    owner: str = Depends(get_current_user_id),
    service: ConversationService = Depends(get_conversation_service),
):
    offset = decode_cursor(cursor)
    page = await service.list_messages(owner, str(conversation_id), limit, offset)
    return MessageList(
        items=[MessageResponse.model_validate(row) for row in page.items],
        next_cursor=encode_next_cursor(offset, limit, page.has_more),
    )


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=201)
async def create_message(
    conversation_id: UUID,
    payload: MessageCreate,
    owner: str = Depends(get_current_user_id),
    service: ConversationService = Depends(get_conversation_service),
):
    row = await service.send_message(owner, str(conversation_id), payload.content_text)
    return MessageResponse.model_validate(row)
