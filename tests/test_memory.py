"""Tests de la memoria: saneado de user_id, persistencia y conflicto de confianza."""
import json

import pytest

import memory
from memory import InvalidUserId, MemoryStore, WorkingMemory, safe_user_dir

USER_IDS_INVALIDOS = ["", "   ", "..", ".", "../..", "a/b", "a\\b", "C:/tmp", "-x", "x" * 65, "..\\tmp"]


def test_user_id_valido_crea_el_directorio_en_data_dir():
    store = MemoryStore("ana")
    assert store.base.parent == memory.DATA_DIR
    assert store.base.is_dir()
    assert store.json_path.name == "memory.json"


@pytest.mark.parametrize("user_id", USER_IDS_INVALIDOS)
def test_user_id_invalido_es_rechazado(user_id):
    with pytest.raises(InvalidUserId):
        safe_user_dir(user_id)
    with pytest.raises(InvalidUserId):
        MemoryStore(user_id)


def test_no_escribe_fuera_de_data_dir():
    """Regresion del path traversal: '..' ya no escapa de data/."""
    with pytest.raises(InvalidUserId):
        MemoryStore("..")
    with pytest.raises(InvalidUserId):
        MemoryStore("../otra")
    assert not (memory.DATA_DIR.parent / "memory.json").exists()


def test_user_id_no_str_es_rechazado():
    with pytest.raises(InvalidUserId):
        MemoryStore({"no": "str"})


def test_semantic_set_no_pisa_un_dato_del_usuario():
    store = MemoryStore("ana")
    assert store.semantic_set("email", "ana@acme.com", confidence=1.0, source="usuario")["ok"]
    resultado = store.semantic_set("email", "ana@otra.com", confidence=1.0, source="llm")
    assert resultado["ok"] is False
    assert store.semantic_get("email") == "ana@acme.com"


def test_semantic_set_reporta_el_descarte_sin_fingir_exito():
    store = MemoryStore("ana")
    store.semantic_set("email", "ana@acme.com", confidence=1.0, source="usuario")
    resultado = store.semantic_set("email", "dudoso@x.com", confidence=0.2, source="llm")
    assert resultado["ok"] is False
    assert "reason" in resultado


def test_semantic_set_actualiza_cuando_aporta_mas_confianza():
    store = MemoryStore("ana")
    store.semantic_set("ciudad", "Madrid", confidence=0.5, source="llm")
    store.semantic_set("ciudad", "Valencia", confidence=0.9, source="llm")
    assert store.semantic_get("ciudad") == "Valencia"


def test_semantic_set_valida_entradas():
    store = MemoryStore("ana")
    assert store.semantic_set("  ", "x")["ok"] is False
    assert store.semantic_set("k", "v", confidence="no-es-un-numero")["ok"] is False


def test_guardado_atomico_deja_backup_utilizable():
    store = MemoryStore("ana")
    store.semantic_set("nombre", "Ana", confidence=1.0, source="usuario")
    store.semantic_set("ciudad", "Madrid", confidence=1.0, source="usuario")
    assert store.backup_path.exists()
    # el backup es un JSON valido (estado anterior, con 'nombre')
    assert "nombre" in json.loads(store.backup_path.read_text(encoding="utf-8"))["semantic"]


def test_recupera_del_backup_si_memory_json_esta_corrupto():
    store = MemoryStore("ana")
    store.semantic_set("nombre", "Ana", confidence=1.0, source="usuario")
    store.semantic_set("ciudad", "Madrid", confidence=1.0, source="usuario")
    store.json_path.write_text('{"semantic": {"nombre"', encoding="utf-8")  # truncado

    recuperado = MemoryStore("ana")
    assert recuperado.semantic_get("nombre") == "Ana"


def test_falla_explicito_si_no_hay_backup_valido():
    """Antes devolvia memoria vacia en silencio: ahora es un error visible."""
    store = MemoryStore("ana")
    store.semantic_set("nombre", "Ana", confidence=1.0, source="usuario")
    store.json_path.write_text("no es json", encoding="utf-8")
    store.backup_path.unlink(missing_ok=True)

    with pytest.raises(RuntimeError):
        MemoryStore("ana")


def test_episodic_recorta_en_memory_json_pero_es_append_only_en_el_log():
    store = MemoryStore("ana")
    for i in range(320):
        store.episodic_add("evt", {"i": i})
    assert len(store._data["episodic"]) == memory.EPISODIC_MEMORY_LIMIT
    lineas = store.episodic_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lineas) == 320


def test_episodic_rota_al_superar_el_tamano_maximo(monkeypatch):
    monkeypatch.setattr(memory, "EPISODIC_FILE_MAX_BYTES", 10)
    store = MemoryStore("ana")
    store.episodic_add("evt", {"i": 1})
    store.episodic_add("evt", {"i": 2})
    assert (store.base / "episodic.1.jsonl").exists()
    assert store.episodic_path.exists()  # se sigue escribiendo en el log activo


def test_procedural_versiona():
    store = MemoryStore("ana")
    assert store.procedural_set("briefing", [{"tool": "gmail_list"}], "resumen")["version"] == 1
    assert store.procedural_set("briefing", [], "resumen v2")["version"] == 2
    assert store.procedural_get("briefing") == []


def test_goal_add_valida_y_ordena():
    store = MemoryStore("ana")
    assert store.goal_add("lanzar agencia", "90")["ok"] is True
    assert store.goal_add("otro", 10)["ok"] is True
    assert store.goal_add("", 50)["ok"] is False
    assert store.goal_list()[0]["description"] == "lanzar agencia"
    assert store.goal_top()["priority"] == 90


def test_clear_borra_datos_y_logs():
    store = MemoryStore("ana")
    store.semantic_set("nombre", "Ana")
    store.episodic_add("evt", {"i": 1})
    store.clear()
    assert store.semantic_all() == {}
    assert store.episodic_recent() == []
    assert not store.episodic_path.exists()


def test_workingmemory_respeta_el_tope():
    working = WorkingMemory(cap=3)
    for i in range(5):
        working.add("user", f"m{i}")
    assert [m["content"] for m in working.all()] == ["m2", "m3", "m4"]
    working.clear()
    assert working.all() == []


def test_snapshot_incluye_user_id_y_claves_esperadas():
    snap = MemoryStore("ana").snapshot()
    assert snap["user_id"] == "ana"
    assert set(snap) >= {"semantic", "semantic_meta", "procedural", "goals", "episodic_recent"}
