"""Tests del orquestador: invariante de aprobacion, ejecucion de tools y bucle de chat."""
import inspect
from types import SimpleNamespace

import pytest

import agent
from config import TOOL_EFFECTS
from memory import MemoryStore, WorkingMemory
from tools import ALL_SCHEMAS


@pytest.fixture
def store():
    return MemoryStore("tester")


def _respuesta_texto(texto):
    from google.genai import types

    return SimpleNamespace(
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=[types.Part(text=texto)]))],
        text=texto,
    )


def _respuesta_tool_call(nombre, args):
    from google.genai import types

    parte = types.Part(function_call=types.FunctionCall(name=nombre, args=args))
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=[parte]))],
        text=None,
    )


class _FakeModels:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)

    def generate_content(self, **kwargs):
        return self.respuestas.pop(0)


# --------------------------------------------------------------- invariante
def test_safe_mode_es_true_por_defecto():
    assert inspect.signature(agent.chat).parameters["safe_mode"].default is True


def test_handlers_cubren_todos_los_schemas(store):
    assert sorted(agent._handlers_for(store)) == sorted(s["name"] for s in ALL_SCHEMAS)


def test_todas_las_tools_tienen_efecto_declarado():
    for schema in ALL_SCHEMAS:
        assert schema["name"] in TOOL_EFFECTS, schema["name"]


def test_run_tool_bloquea_envios_y_lo_registra(store):
    llamado = {"n": 0}

    def handler(**kwargs):
        llamado["n"] += 1
        return {"status": "sent"}

    out = agent.run_tool("gmail_send", {"to": "a@b.com"}, {"gmail_send": handler}, store, safe_mode=True)
    assert "Bloqueado" in out["error"]
    assert llamado["n"] == 0
    assert store.episodic_recent(1)[0]["type"] == "tool_blocked"


def test_run_tool_permite_envios_fuera_de_modo_seguro(store):
    handlers = {"gmail_send": lambda **kwargs: {"status": "sent"}}
    out = agent.run_tool("gmail_send", {"to": "a@b.com"}, handlers, store, safe_mode=False)
    assert out == {"status": "sent"}
    assert store.episodic_recent(1)[0]["payload"]["ok"] is True


def test_run_tool_gatea_calendar_create_solo_con_invitados(store):
    handlers = {"calendar_create": lambda **kwargs: {"id": "E1"}}
    privado = agent.run_tool("calendar_create", {"title": "x", "start": "2026-01-01"}, handlers, store)
    assert "error" not in privado
    con_invitados = agent.run_tool(
        "calendar_create",
        {"title": "x", "start": "2026-01-01", "attendees": ["a@b.com"]},
        handlers,
        store,
    )
    assert "Bloqueado" in con_invitados["error"]


def test_run_tool_registra_tool_desconocida(store):
    out = agent.run_tool("no_existe", {}, {}, store)
    assert "tool desconocida" in out["error"]
    assert store.episodic_recent(1)[0]["type"] == "tool_unknown"


def test_run_tool_captura_errores_del_handler(store):
    def handler(**kwargs):
        raise RuntimeError("la API respondio 403")

    out = agent.run_tool("gmail_list", {}, {"gmail_list": handler}, store, safe_mode=False)
    assert "403" in out["error"]
    assert store.episodic_recent(1)[0]["type"] == "tool_error"


def test_run_tool_captura_argumentos_invalidos(store):
    handlers = {"gmail_list": lambda max_results=10: {"messages": []}}
    out = agent.run_tool("gmail_list", {"parametro_inexistente": 1}, handlers, store, safe_mode=False)
    assert "argumentos invalidos" in out["error"]


def test_run_tool_envuelve_resultados_no_dict(store):
    out = agent.run_tool("gmail_list", {}, {"gmail_list": lambda: ["a"]}, store, safe_mode=False)
    assert out == {"result": ["a"]}


def test_build_tool_es_valido_para_google_genai():
    pytest.importorskip("google.genai")
    assert len(agent._build_tool().function_declarations) == len(ALL_SCHEMAS)


# --------------------------------------------------------------- bucle de chat
def test_chat_sin_api_key_avisa(monkeypatch, store):
    monkeypatch.setattr(agent, "GEMINI_API_KEY", "")
    monkeypatch.setattr(agent, "_client", None)
    assert "GEMINI_API_KEY" in agent.chat("hola", WorkingMemory(), store)


def test_chat_respeta_el_modo_seguro_en_el_bucle(monkeypatch, store):
    monkeypatch.setattr(
        agent,
        "_client",
        SimpleNamespace(models=_FakeModels([
            _respuesta_tool_call("discord_send", {"content": "hola"}),
            _respuesta_texto("No puedo enviarlo en modo seguro."),
        ])),
    )
    working = WorkingMemory()
    working.add("user", "manda hola a discord")
    salida = agent.chat("manda hola a discord", working, store, safe_mode=True)
    assert salida == "No puedo enviarlo en modo seguro."
    tipos = [e["type"] for e in store.episodic_recent(20)]
    assert "tool_blocked" in tipos
    assert "assistant_message" in tipos


def test_chat_ejecuta_tools_cuando_no_hay_modo_seguro(monkeypatch, store):
    monkeypatch.setattr(
        agent,
        "_client",
        SimpleNamespace(models=_FakeModels([
            _respuesta_tool_call("add_goal", {"description": "lanzar agencia", "priority": 90}),
            _respuesta_texto("objetivo guardado"),
        ])),
    )
    assert agent.chat("objetivo: lanzar agencia", WorkingMemory(), store, safe_mode=False) == "objetivo guardado"
    assert store.goal_top()["description"] == "lanzar agencia"


def test_chat_anade_el_mensaje_actual_si_la_memoria_de_trabajo_esta_vacia(monkeypatch, store):
    capturado = {}

    class _Models:
        def generate_content(self, **kwargs):
            capturado["contents"] = list(kwargs["contents"])
            return _respuesta_texto("hola")

    monkeypatch.setattr(agent, "_client", SimpleNamespace(models=_Models()))
    assert agent.chat("hola", WorkingMemory(), store) == "hola"
    assert capturado["contents"][-1].role == "user"


def test_chat_no_duplica_el_mensaje_si_ya_esta_en_la_memoria(monkeypatch, store):
    capturado = {}

    class _Models:
        def generate_content(self, **kwargs):
            capturado["contents"] = list(kwargs["contents"])
            return _respuesta_texto("hola")

    monkeypatch.setattr(agent, "_client", SimpleNamespace(models=_Models()))
    working = WorkingMemory()
    working.add("user", "hola")
    agent.chat("hola", working, store)
    assert len(capturado["contents"]) == 1


def test_chat_avisa_al_agotar_los_pasos(monkeypatch, store):
    respuestas = [_respuesta_tool_call("list_goals", {}) for _ in range(3)]
    monkeypatch.setattr(agent, "_client", SimpleNamespace(models=_FakeModels(respuestas)))
    salida = agent.chat("dame mis objetivos", WorkingMemory(), store, max_steps=3)
    assert "maximo de 3 pasos" in salida


def test_chat_avisa_si_el_modelo_no_devuelve_candidatos(monkeypatch, store):
    monkeypatch.setattr(
        agent,
        "_client",
        SimpleNamespace(models=_FakeModels([SimpleNamespace(candidates=[], text=None)])),
    )
    assert "Sin respuesta" in agent.chat("hola", WorkingMemory(), store)


def test_system_prompt_incluye_memoria_reciente(store):
    store.semantic_set("nombre", "Ana", confidence=1.0, source="usuario")
    store.goal_add("lanzar agencia", 90)
    store.episodic_add("tool_call", {"tool": "gmail_list", "ok": True, "args": {}})
    prompt = agent._system_prompt(store)
    assert "Ana" in prompt
    assert "lanzar agencia" in prompt
    assert "Actividad reciente" in prompt
