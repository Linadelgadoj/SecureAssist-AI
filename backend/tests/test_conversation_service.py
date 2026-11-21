"""Casos de uso de conversaciones probados sin HTTP, con el repositorio en memoria."""
import asyncio

import pytest

from app.application.conversations import DEFAULT_TITLE, ConversationService
from app.domain.errors import NotFoundError
from app.repositories.memory_conversations import InMemoryConversationRepository

OWNER = "64de01b6-9520-4cf4-8b22-2c64af080fe7"
OTHER = "7382fdc4-b5ad-4b2e-916e-36a0c8532f17"


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def service():
    return ConversationService(InMemoryConversationRepository())


def test_start_conversation_uses_default_title_when_missing(service):
    assert run(service.start_conversation(OWNER, None))["title"] == DEFAULT_TITLE
    assert run(service.start_conversation(OWNER, "DVR sin señal"))["title"] == "DVR sin señal"


def test_list_conversations_reports_more_pages(service):
    for _ in range(3):
        run(service.start_conversation(OWNER, None))
    first = run(service.list_conversations(OWNER, limit=2, offset=0))
    last = run(service.list_conversations(OWNER, limit=2, offset=2))
    assert (len(first.items), first.has_more) == (2, True)
    assert (len(last.items), last.has_more) == (1, False)


def test_foreign_conversation_is_not_found_for_reads_and_writes(service):
    conversation = run(service.start_conversation(OTHER, "Privada"))
    with pytest.raises(NotFoundError):
        run(service.get_conversation(OWNER, conversation["id"]))
    with pytest.raises(NotFoundError):
        run(service.list_messages(OWNER, conversation["id"], limit=10, offset=0))
    with pytest.raises(NotFoundError):
        run(service.send_message(OWNER, conversation["id"], "hola"))


def test_send_message_is_listed_in_order(service):
    conversation = run(service.start_conversation(OWNER, None))
    run(service.send_message(OWNER, conversation["id"], "primero"))
    run(service.send_message(OWNER, conversation["id"], "segundo"))
    page = run(service.list_messages(OWNER, conversation["id"], limit=10, offset=0))
    assert [m["content_text"] for m in page.items] == ["primero", "segundo"]
