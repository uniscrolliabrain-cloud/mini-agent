"""Tests de Calendar, Discord y busqueda web (sin red)."""
import pytest

import tools.calendar as calendar_tool
import tools.discord as discord_tool
import tools.gmail as gmail_tool
import tools.search as search_tool
from config import DEFAULT_TIMEZONE
from conftest import FakeResponse

EVENTO_OK = FakeResponse(payload={"id": "E1", "htmlLink": "https://cal/E1"})


# ------------------------------------------------------------------ Calendar
def test_calendar_create_todo_el_dia_usa_date_y_duracion_de_un_dia(install_fake_http):
    fake = install_fake_http(calendar_tool, (None, "/events", EVENTO_OK))
    calendar_tool.calendar_create("Cita", "2026-09-22")
    body = fake.calls[0]["json"]
    assert body["start"] == {"date": "2026-09-22"}
    assert body["end"] == {"date": "2026-09-23"}
    assert "dateTime" not in body["start"]


def test_calendar_create_sin_offset_anade_timezone_y_una_hora(install_fake_http):
    fake = install_fake_http(calendar_tool, (None, "/events", EVENTO_OK))
    calendar_tool.calendar_create("Reunion", "2026-09-22T10:00:00")
    body = fake.calls[0]["json"]
    assert body["start"] == {"dateTime": "2026-09-22T10:00:00", "timeZone": DEFAULT_TIMEZONE}
    assert body["end"] == {"dateTime": "2026-09-22T11:00:00", "timeZone": DEFAULT_TIMEZONE}


def test_calendar_create_con_offset_no_anade_timezone(install_fake_http):
    fake = install_fake_http(calendar_tool, (None, "/events", EVENTO_OK))
    calendar_tool.calendar_create("Reunion", "2026-09-22T10:00:00+02:00")
    assert fake.calls[0]["json"]["start"] == {"dateTime": "2026-09-22T10:00:00+02:00"}


def test_calendar_create_respeta_el_fin_indicado(install_fake_http):
    fake = install_fake_http(calendar_tool, (None, "/events", EVENTO_OK))
    calendar_tool.calendar_create("Reunion", "2026-09-22T10:00:00", "2026-09-22T12:30:00")
    assert fake.calls[0]["json"]["end"]["dateTime"] == "2026-09-22T12:30:00"


@pytest.mark.parametrize("fecha", ["", "   ", "22/09/2026", "2026-13-01", "manana"])
def test_calendar_create_rechaza_fechas_invalidas(install_fake_http, fecha):
    install_fake_http(calendar_tool, (None, "/events", EVENTO_OK))
    with pytest.raises(ValueError):
        calendar_tool.calendar_create("Cita", fecha)


def test_calendar_create_acepta_attendees_como_texto(install_fake_http):
    fake = install_fake_http(calendar_tool, (None, "/events", EVENTO_OK))
    out = calendar_tool.calendar_create("Cita", "2026-09-22", attendees="ana@acme.com, luis@acme.com")
    assert fake.calls[0]["json"]["attendees"] == [{"email": "ana@acme.com"}, {"email": "luis@acme.com"}]
    assert out["invited"] == ["ana@acme.com", "luis@acme.com"]


def test_calendar_list_incluye_eventos_de_todo_el_dia(install_fake_http):
    payload = {
        "items": [
            {"id": "1", "summary": "Feriado", "start": {"date": "2026-09-22"}, "end": {"date": "2026-09-23"}},
            {
                "id": "2",
                "summary": "Reunion",
                "start": {"dateTime": "2026-09-22T10:00:00+02:00"},
                "end": {"dateTime": "2026-09-22T11:00:00+02:00"},
            },
        ]
    }
    fake = install_fake_http(calendar_tool, (None, "/events", FakeResponse(payload=payload)))
    eventos = calendar_tool.calendar_list(max_results=999)["events"]
    assert eventos[0]["start"] == "2026-09-22"
    assert eventos[0]["all_day"] is True
    assert eventos[1]["all_day"] is False
    assert fake.calls[0]["params"]["maxResults"] == 250


# ------------------------------------------------------------------ Discord
def test_discord_sin_token_error_explicito():
    with pytest.raises(RuntimeError) as excinfo:
        discord_tool.discord_send("hola", "123")
    assert "DISCORD_BOT_TOKEN" in str(excinfo.value)


def test_discord_sin_canal_error_explicito(monkeypatch):
    monkeypatch.setattr(discord_tool, "DISCORD_BOT_TOKEN", "token-de-test")
    with pytest.raises(RuntimeError) as excinfo:
        discord_tool.discord_send("hola", "")
    assert "channel_id" in str(excinfo.value)


def test_discord_send_trunca_avisando(install_fake_http, monkeypatch):
    monkeypatch.setattr(discord_tool, "DISCORD_BOT_TOKEN", "token-de-test")
    fake = install_fake_http(discord_tool, (None, "messages", FakeResponse(payload={"id": "1"})))
    out = discord_tool.discord_send("x" * 5000, "123")
    assert out["truncated"] is True
    assert fake.calls[0]["json"]["content"].endswith("[...]")
    assert len(fake.calls[0]["json"]["content"]) <= discord_tool.MAX_CONTENT


def test_discord_send_rechaza_contenido_vacio(monkeypatch):
    monkeypatch.setattr(discord_tool, "DISCORD_BOT_TOKEN", "token-de-test")
    assert "error" in discord_tool.discord_send("   ", "123")


def test_discord_read_acota_el_limite(install_fake_http, monkeypatch):
    monkeypatch.setattr(discord_tool, "DISCORD_BOT_TOKEN", "token-de-test")
    fake = install_fake_http(
        discord_tool,
        (None, "messages", FakeResponse(payload=[{"id": "1", "author": {"username": "ana"}, "content": "hola"}])),
    )
    out = discord_tool.discord_read("123", limit=99999)
    assert fake.calls[0]["params"]["limit"] == 100
    assert out["messages"] == [{"id": "1", "author": "ana", "content": "hola"}]


def test_discord_rate_limit_da_un_mensaje_util(install_fake_http, monkeypatch):
    monkeypatch.setattr(discord_tool, "DISCORD_BOT_TOKEN", "token-de-test")
    install_fake_http(
        discord_tool,
        (None, "messages", FakeResponse(status_code=429, text="rate limited", headers={"retry-after": "3"})),
    )
    with pytest.raises(RuntimeError) as excinfo:
        discord_tool.discord_send("hola", "123")
    assert "rate limit" in str(excinfo.value)
    assert "3" in str(excinfo.value)


# ------------------------------------------------------------------ Busqueda web
class _FakeDDGS:
    results = []
    error = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def text(self, query, max_results=5):
        if type(self).error:
            raise type(self).error
        return type(self).results


def _fake_ddgs(results=None, error=None):
    """Devuelve un sustituto de `_ddgs_class` con los resultados indicados."""
    clase = type("DDGSStub", (_FakeDDGS,), {"results": results or [], "error": error})
    return lambda: clase


def test_web_search_normaliza_resultados(monkeypatch):
    monkeypatch.setattr(
        search_tool, "_ddgs_class", _fake_ddgs([{"title": "T", "href": "http://x", "body": "b" * 500}])
    )
    out = search_tool.web_search("python")
    assert out["results"][0]["url"] == "http://x"
    assert len(out["results"][0]["snippet"]) == 300


def test_web_search_acepta_url_en_clave_url(monkeypatch):
    monkeypatch.setattr(search_tool, "_ddgs_class", _fake_ddgs([{"title": "T", "url": "http://y", "body": "b"}]))
    assert search_tool.web_search("python")["results"][0]["url"] == "http://y"


def test_web_search_sin_resultados_lo_reporta_como_error(monkeypatch):
    """Regresion: una lista vacia se devolvia sin error y parecia que no habia nada."""
    monkeypatch.setattr(search_tool, "_ddgs_class", _fake_ddgs([]))
    out = search_tool.web_search("python")
    assert out["results"] == []
    assert "sin resultados" in out["error"]


def test_web_search_sin_libreria_explica_que_falta(monkeypatch):
    def _boom():
        raise RuntimeError("falta la dependencia de busqueda web: pip install ddgs")

    monkeypatch.setattr(search_tool, "_ddgs_class", _boom)
    out = search_tool.web_search("python")
    assert "ddgs" in out["error"]


def test_web_search_con_excepcion_del_buscador(monkeypatch):
    monkeypatch.setattr(search_tool, "_ddgs_class", _fake_ddgs(error=RuntimeError("bloqueado por DDG")))
    out = search_tool.web_search("python")
    assert "bloqueado por DDG" in out["error"]


def test_web_search_query_vacia():
    assert search_tool.web_search("   ")["error"] == "query vacia"


def test_email_search_combina_gmail_y_web(monkeypatch, install_fake_http):
    install_fake_http(gmail_tool, (None, "messages", FakeResponse(payload={"messages": []})))
    monkeypatch.setattr(search_tool, "_ddgs_class", _fake_ddgs([{"title": "T", "href": "http://x", "body": "b"}]))
    out = search_tool.email_search("juan")
    assert out["gmail"] == {"messages": []}
    assert out["web"]["results"][0]["title"] == "T"


def test_email_search_query_vacia():
    assert search_tool.email_search("")["error"] == "query vacia"
