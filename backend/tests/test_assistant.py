"""Asistente con un modelo falso (determinista) y adaptador de Ollama con transporte simulado."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.application.assistant import MAX_TOOL_ROUNDS, AssistantService
from app.application.assistant_tools import AssistantTools, rank_products
from app.domain.assistant import AssistantUnavailable, ChatTurn, ModelReply, ToolCall, ToolSpec
from app.domain.errors import ConflictError, NotFoundError
from app.main import create_app
from app.repositories.memory_conversations import InMemoryConversationRepository
from app.services.ollama_provider import OllamaLanguageModel
from postgres_support import login, make_settings

OWNER = "64de01b6-9520-4cf4-8b22-2c64af080fe7"


def run(coro):
    return asyncio.run(coro)


def product(sku, name, total, stock, **extra):
    return {"sku": sku, "name": name, "brand": extra.get("brand"), "model": None, "category": extra.get("category", "x"),
            "unit": "unidad", "total_quantity": total, "is_low_stock": total <= extra.get("min_stock", 0),
            "stock": [{"location_name": k, "quantity": v} for k, v in stock.items()]}


class FakeCatalog:
    def __init__(self, products):
        self.products = products

    async def list_products(self, **_):
        return self.products


class ScriptedModel:
    """Devuelve las respuestas en orden y guarda lo que recibió en cada llamada."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[tuple[list[ChatTurn], list[ToolSpec]]] = []

    async def chat(self, turns, tools):
        self.calls.append((list(turns), list(tools)))
        return self.replies.pop(0)

    async def aclose(self):
        return None


CATALOG = FakeCatalog([
    product("FU-12V-2A", "Fuente 12V 2A", 19, {"Bodega principal": 14, "Camioneta 1": 5}, category="fuente"),
    product("CAM-DH-D4MP", "Cámara domo 4MP", 6, {"Bodega principal": 6}, brand="Dahua", category="camara"),
])


def conversation_with(*messages):
    repo = InMemoryConversationRepository()
    conversation = run(repo.create_conversation(OWNER, "Prueba"))
    for role, text in messages:
        create = repo.create_message if role == "installer" else repo.create_assistant_message
        run(create(OWNER, conversation["id"], text))
    return repo, conversation["id"]


def test_reply_is_saved_as_assistant_message_with_history_and_rules():
    repo, conversation_id = conversation_with(("installer", "Hola"), ("assistant", "¿Qué equipo?"),
                                              ("installer", "Un DVR Hikvision que no da video"))
    model = ScriptedModel(ModelReply("1. Revisa la alimentación del DVR."))
    saved = run(AssistantService(repo, model, AssistantTools(CATALOG, None)).reply(OWNER, conversation_id))

    assert (saved["role"], saved["processing_state"]) == ("assistant", "completed")
    turns, tools = model.calls[0]
    assert turns[0].role == "system" and "NUNCA inventes" in turns[0].content
    assert [(t.role, t.content) for t in turns[1:]] == [
        ("user", "Hola"), ("assistant", "¿Qué equipo?"), ("user", "Un DVR Hikvision que no da video")]
    assert [t.name for t in tools] == ["consultar_inventario"]


def test_tool_call_reads_inventory_and_feeds_the_result_back():
    repo, conversation_id = conversation_with(("installer", "¿Tenemos fuentes de 12 voltios?"))
    model = ScriptedModel(
        ModelReply("", (ToolCall("consultar_inventario", {"busqueda": "fuente de poder 12V"}),)),
        ModelReply("Sí: hay 14 en Bodega principal y 5 en Camioneta 1."),
    )
    saved = run(AssistantService(repo, model, AssistantTools(CATALOG, None)).reply(OWNER, conversation_id))

    assert saved["content_text"] == "Sí: hay 14 en Bodega principal y 5 en Camioneta 1."
    tool_turn = model.calls[1][0][-1]
    assert tool_turn.role == "tool" and tool_turn.tool_name == "consultar_inventario"
    result = json.loads(tool_turn.content)
    assert result["resultados"][0]["codigo"] == "FU-12V-2A"
    assert result["resultados"][0]["por_ubicacion"] == {"Bodega principal": 14, "Camioneta 1": 5}


def test_tool_rounds_are_bounded_and_a_final_answer_is_forced():
    repo, conversation_id = conversation_with(("installer", "fuente"))
    loop = ModelReply("", (ToolCall("consultar_inventario", {"busqueda": "fuente"}),))
    model = ScriptedModel(*([loop] * MAX_TOOL_ROUNDS), ModelReply("Respuesta final."))
    saved = run(AssistantService(repo, model, AssistantTools(CATALOG, None)).reply(OWNER, conversation_id))
    assert saved["content_text"] == "Respuesta final."
    assert len(model.calls) == MAX_TOOL_ROUNDS + 1
    assert model.calls[-1][1] == []  # la última llamada va sin herramientas


def test_unknown_or_bad_tool_arguments_do_not_break_the_reply():
    tools = AssistantTools(CATALOG, None)
    assert "error" in json.loads(run(tools.run("borrar_todo", {"busqueda": "x"})))
    assert "error" in json.loads(run(tools.run("consultar_inventario", {"busqueda": 42})))
    assert json.loads(run(tools.run("consultar_inventario", {"busqueda": "zzz"})))["resultados"] == []


def test_nothing_to_reply_and_foreign_conversation():
    repo, conversation_id = conversation_with(("installer", "hola"), ("assistant", "hola, ¿qué pasa?"))
    service = AssistantService(repo, ScriptedModel(), AssistantTools(None, None))
    with pytest.raises(ConflictError) as error:
        run(service.reply(OWNER, conversation_id))
    assert error.value.code == "NOTHING_TO_REPLY"
    with pytest.raises(NotFoundError):
        run(service.reply("7382fdc4-b5ad-4b2e-916e-36a0c8532f17", conversation_id))


def test_empty_model_output_is_reported_as_unavailable():
    repo, conversation_id = conversation_with(("installer", "hola"))
    service = AssistantService(repo, ScriptedModel(ModelReply(""), ModelReply("")), AssistantTools(None, None))
    with pytest.raises(AssistantUnavailable):
        run(service.reply(OWNER, conversation_id))


def test_rank_products_matches_words_and_ignores_accents_and_fillers():
    found = rank_products(CATALOG.products, "camara domo dahua")
    assert [p["sku"] for p in found] == ["CAM-DH-D4MP"]
    assert [p["sku"] for p in rank_products(CATALOG.products, "fuente de poder")] == ["FU-12V-2A"]
    assert rank_products(CATALOG.products, "de la para") == []


# --------------------------------------------------------------------------- adaptador de Ollama

def ollama_with(handler):
    return OllamaLanguageModel("http://ollama.test", "qwen3.5",
                               client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_ollama_adapter_sends_tools_without_thinking_and_parses_calls():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "consultar_inventario", "arguments": {"busqueda": "fuente"}}}]}})

    turns = [ChatTurn("system", "s"), ChatTurn("tool", "{}", tool_name="consultar_inventario")]
    reply = run(ollama_with(handler).chat(turns, [ToolSpec("consultar_inventario", "d", {"type": "object"})]))
    assert reply.tool_calls == (ToolCall("consultar_inventario", {"busqueda": "fuente"}),)
    assert seen["think"] is False and seen["stream"] is False and seen["model"] == "qwen3.5"
    assert seen["tools"][0]["function"]["name"] == "consultar_inventario"
    assert seen["messages"][1] == {"role": "tool", "content": "{}", "tool_name": "consultar_inventario"}


def test_ollama_adapter_maps_failures_to_assistant_unavailable():
    def refused(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(AssistantUnavailable, match="Ollama"):
        run(ollama_with(refused).chat([ChatTurn("user", "hola")], []))
    with pytest.raises(AssistantUnavailable, match="no está instalado"):
        run(ollama_with(lambda r: httpx.Response(404, json={"error": "model not found"})).chat(
            [ChatTurn("user", "hola")], []))


# --------------------------------------------------------------------------- API

def test_reply_endpoint_with_injected_model_and_disabled_assistant():
    with TestClient(create_app(make_settings(database_url=""))) as client:
        headers = login(client)
        conversation = client.post("/api/v1/conversations", json={"title": "DVR"}, headers=headers).json()
        client.post(f"/api/v1/conversations/{conversation['id']}/messages",
                    json={"content_text": "El DVR no enciende"}, headers=headers)

        disabled = client.post(f"/api/v1/conversations/{conversation['id']}/reply", headers=headers)
        assert disabled.status_code == 503
        assert disabled.json()["error"]["code"] == "ASSISTANT_UNAVAILABLE"

        client.app.state.language_model = ScriptedModel(ModelReply("Revisa la fuente con un multímetro."))
        answered = client.post(f"/api/v1/conversations/{conversation['id']}/reply", headers=headers)
        assert answered.status_code == 201
        assert answered.json()["role"] == "assistant"
        messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages", headers=headers).json()
        assert [m["role"] for m in messages["items"]] == ["installer", "assistant"]
