"""Tests de las tools de Google, Discord y busqueda web (sin red)."""
import base64
import email

import pytest

import tools.calendar as calendar_tool
import tools.discord as discord_tool
import tools.drive as drive_tool
import tools.gmail as gmail_tool
import tools.search as search_tool
from config import DEFAULT_TIMEZONE
from conftest import FakeResponse


# ------------------------------------------------------------------ Gmail
def test_gmail_send_codifica_utf8_y_asunto_rfc2047(install_fake_http):
    fake = install_fake_http(gmail_tool, (None, "messages/send", FakeResponse(payload={"id": "M1"})))
    out = gmail_tool.gmail_send("ana@acme.com", "Reunión de mañana", "¿Confirmas? Sí/No")
    assert out["status"] == "sent"

    mensaje = base64.urlsafe_b64decode(fake.calls[0]["json"]["raw"].encode()).decode("utf-8")
    parsed = email.message_from_string(mensaje)
    assert parsed.get_content_charset() == "utf-8"
    assert parsed.get_payload(decode=True).decode("utf-8") == "¿Confirmas? Sí/No"
    assert "=?utf-8?" in mensaje  # el asunto va codificado (RFC 2047)


def test_gmail_send_incluye_el_motivo_del_error_de_google(install_fake_http):
    install_fake_http(
        gmail_tool,
        (None, "messages/send", FakeResponse(status_code=403, text='{"error":"insufficientPermissions"}')),
    )
    with pytest.raises(RuntimeError) as excinfo:
        gmail_tool.gmail_send("ana@acme.com", "Hola", "cuerpo")
    assert "403" in str(excinfo.value)
    assert "insufficientPermissions" in str(excinfo.value)


def test_gmail_list_acota_max_results(install_fake_http):
    fake = install_fake_http(gmail_tool, (None, "messages", FakeResponse(payload={"messages": []})))
    gmail_tool.gmail_list(max_results=500)
    assert fake.calls[0]["params"]["maxResults"] == 100
    gmail_tool.gmail_list(max_results="no-numero")
    assert fake.calls[1]["params"]["maxResults"] == 10


def test_gmail_list_lee_cabeceras_y_fecha(install_fake_http):
    payload_mensaje = {
        "snippet": "hola",
        "payload": {"headers": [{"name": "From", "value": "ana@acme.com"}, {"name": "Subject", "value": "Hola"},
                                {"name": "Date", "value": "Tue, 22 Sep 2026 10:00:00 +0200"}]},
    }
    install_fake_http(
        gmail_tool,
        ("GET", "/messages/ID1", FakeResponse(payload=payload_mensaje)),
        ("GET", "/messages", FakeResponse(payload={"messages": [{"id": "ID1"}]})),
    )
    out = gmail_tool.gmail_list()
    assert out["messages"][0]["from"] == "ana@acme.com"
    assert out["messages"][0]["date"].startswith("Tue, 22 Sep 2026")


# ------------------------------------------------------------------ Drive
def test_drive_search_escapa_las_comillas(install_fake_http):
    fake = install_fake_http(drive_tool, (None, "files", FakeResponse(payload={"files": []})))
    out = drive_tool.drive_search("O'Brien")
    assert fake.calls[0]["params"]["q"] == "name contains 'O\\'Brien' and trashed=false"
    assert out["query"] == fake.calls[0]["params"]["q"]


def test_drive_list_escapa_el_folder_id(install_fake_http):
    fake = install_fake_http(drive_tool, (None, "files", FakeResponse(payload={"files": []})))
    drive_tool.drive_list("a'b")
    assert fake.calls[0]["params"]["q"] == "trashed=false and 'a\\'b' in parents"


def test_drive_read_spreadsheet_usa_files_export(install_fake_http):
    def router(**kwargs):
        if "/export" in kwargs.get("url", ""):
            return FakeResponse(text="a,b\n1,2")
        return FakeResponse(payload={"id": "SHEET", "name": "Hoja", "mimeType": "application/vnd.google-apps.spreadsheet"})

    fake = install_fake_http(drive_tool, (None, None, router))
    out = drive_tool.drive_read("SHEET")
    assert any("/export" in url for url in fake.urls())
    assert not any((c.get("params") or {}).get("alt") == "media" for c in fake.calls)
    assert out["exported_as"] == "text/csv"
    assert out["content"] == "a,b\n1,2"


def test_drive_read_fichero_de_texto_usa_alt_media(install_fake_http):
    def router(**kwargs):
        if (kwargs.get("params") or {}).get("alt") == "media":
            return FakeResponse(text="contenido de la nota")
        return FakeResponse(payload={"id": "NOTE", "name": "nota.txt", "mimeType": "text/plain"})

    fake = install_fake_http(drive_tool, (None, None, router))
    out = drive_tool.drive_read("NOTE")
    assert out["content"] == "contenido de la nota"
    assert any((c.get("params") or {}).get("alt") == "media" for c in fake.calls)


def test_drive_read_binario_no_descarga(install_fake_http):
    fake = install_fake_http(
        drive_tool,
        (None, "files/BIN", FakeResponse(payload={"id": "BIN", "name": "foto.png", "mimeType": "image/png"})),
    )
    out = drive_tool.drive_read("BIN")
    assert "binario" in out["content"]
    assert len(fake.calls) == 1  # solo metadatos, no descarga


def test_drive_read_google_apps_no_soportado_explica(install_fake_http):
    install_fake_http(
        drive_tool,
        (None, "files/FORM", FakeResponse(payload={"id": "FORM", "name": "Form", "mimeType": "application/vnd.google-apps.form"})),
    )
    out = drive_tool.drive_read("FORM")
    assert "no se puede exportar" in out["content"]


def test_drive_read_propaga_errores(install_fake_http):
    install_fake_http(drive_tool, (None, "files/X", FakeResponse(status_code=404, text='{"error":{"code":404}}')))
    with pytest.raises(RuntimeError) as excinfo:
        drive_tool.drive_read("X")
    assert "404" in str(excinfo.value)
