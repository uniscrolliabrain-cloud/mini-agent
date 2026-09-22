"""Tests de la API HTTP: autenticacion, validacion de user_id, CORS y endpoints."""
import pytest
from fastapi.testclient import TestClient

import api
import memory

CLIENT = TestClient(api.app)
HEADERS = {"X-API-Key": "test-api-key"}


@pytest.fixture
def chat_stub(monkeypatch):
    monkeypatch.setattr(api, "chat", lambda *args, **kwargs: "respuesta stub")


def test_health_no_requiere_auth():
    r = CLIENT.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chat_sin_key_devuelve_401():
    assert CLIENT.post("/chat", json={"message": "hola"}).status_code == 401


def test_chat_con_key_incorrecta_devuelve_401():
    r = CLIENT.post("/chat", json={"message": "hola"}, headers={"X-API-Key": "otra"})
    assert r.status_code == 401


def test_chat_con_key_responde_y_devuelve_snapshot(chat_stub):
    r = CLIENT.post("/chat", json={"message": "hola", "user_id": "ana"}, headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "respuesta stub"
    assert body["snapshot"]["user_id"] == "ana"


def test_chat_con_mensaje_vacio_es_rechazado(chat_stub):
    assert CLIENT.post("/chat", json={"message": ""}, headers=HEADERS).status_code == 422


def test_safe_mode_por_defecto_en_el_modelo_de_entrada():
    assert api.ChatIn(message="hola").safe_mode is True


def test_chat_user_id_con_traversal_es_rechazado(chat_stub):
    assert CLIENT.post("/chat", json={"message": "hola", "user_id": ".."}, headers=HEADERS).status_code == 422


@pytest.mark.parametrize("malicioso", ["%2E%2E", "a%2Fb", "a%5Cb", "%2E"])
def test_memory_con_user_id_peligroso_es_rechazado(malicioso):
    r = CLIENT.get(f"/memory/{malicioso}", headers=HEADERS)
    assert r.status_code in (400, 404, 422)
    # y no se ha escrito nada fuera de DATA_DIR
    assert not (memory.DATA_DIR.parent / "memory.json").exists()


def test_memory_requiere_key():
    assert CLIENT.get("/memory/ana").status_code == 401
    assert CLIENT.delete("/memory/ana").status_code == 401


def test_memory_get_y_delete_con_key():
    store, _ = api.get_store("ana")
    store.semantic_set("nombre", "Ana", confidence=1.0, source="usuario")

    r = CLIENT.get("/memory/ana", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["semantic"]["nombre"] == "Ana"

    assert CLIENT.delete("/memory/ana", headers=HEADERS).status_code == 200
    assert CLIENT.get("/memory/ana", headers=HEADERS).json()["semantic"] == {}


def test_cors_solo_permite_los_origenes_configurados():
    permitido = CLIENT.options(
        "/chat",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert permitido.headers.get("access-control-allow-origin") == "http://localhost:5173"

    ajeno = CLIENT.options(
        "/chat",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in ajeno.headers


def test_la_cache_de_usuarios_esta_acotada(monkeypatch):
    monkeypatch.setattr(api, "MAX_CACHED_USERS", 3)
    for i in range(6):
        api.get_store(f"u{i}")
    assert len(api._stores) <= 3
    assert len(api._workings) <= 3


def test_get_store_reutiliza_la_misma_instancia():
    store_a, working_a = api.get_store("ana")
    store_b, working_b = api.get_store("ana")
    assert store_a is store_b
    assert working_a is working_b


def test_sin_admin_api_key_la_api_no_atiende(monkeypatch):
    monkeypatch.setattr(api, "ADMIN_API_KEY", "")
    r = CLIENT.post("/chat", json={"message": "hola"}, headers=HEADERS)
    assert r.status_code == 503
