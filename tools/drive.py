"""Google Drive API: listar, leer y buscar ficheros."""
import httpx

from google_auth import headers

from ._util import escape_drive_query

BASE = "https://www.googleapis.com/drive/v3"
TIMEOUT = 30
TEXT_LIMIT = 15000

# Los ficheros de Google Workspace no se descargan con alt=media: hay que exportarlos.
# https://developers.google.com/workspace/drive/api/reference/rest/v3/files/get
EXPORT_MIME = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

# Tipos que se pueden leer tal cual con alt=media
TEXTUAL_MIME = {
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-yaml",
    "application/csv",
}


def _check(r: httpx.Response, action: str) -> None:
    if r.status_code >= 400:
        raise RuntimeError(f"{action} fallo ({r.status_code}): {r.text[:300]}")


def drive_list(folder_id: str = "") -> dict:
    q = "trashed=false"
    if folder_id:
        q += f" and '{escape_drive_query(folder_id)}' in parents"
    r = httpx.get(
        f"{BASE}/files",
        headers=headers(),
        params={"q": q, "fields": "files(id,name,mimeType,size,modifiedTime)", "pageSize": 50},
        timeout=TIMEOUT,
    )
    _check(r, "drive_list")
    return {"files": r.json().get("files", [])}


def drive_read(file_id: str) -> dict:
    meta_r = httpx.get(
        f"{BASE}/files/{file_id}",
        headers=headers(),
        params={"fields": "id,name,mimeType,size"},
        timeout=TIMEOUT,
    )
    _check(meta_r, "drive_read (metadata)")
    meta = meta_r.json()
    mime = meta.get("mimeType", "")
    fid = meta.get("id", file_id)
    info = {"id": fid, "name": meta.get("name", ""), "mimeType": mime}

    if mime in EXPORT_MIME:
        export_as = EXPORT_MIME[mime]
        r = httpx.get(
            f"{BASE}/files/{fid}/export",
            headers=headers(),
            params={"mimeType": export_as},
            timeout=TIMEOUT,
        )
        _check(r, "drive_read (export)")
        return {**info, "exported_as": export_as, "content": r.text[:TEXT_LIMIT]}

    if mime.startswith("application/vnd.google-apps"):
        return {
            **info,
            "content": (
                f"[{mime} no se puede exportar como texto con esta tool. "
                "Tipos soportados: Document, Spreadsheet, Presentation]"
            ),
        }

    if not (mime.startswith("text/") or mime in TEXTUAL_MIME):
        return {
            **info,
            "content": f"[archivo binario {mime} no legible como texto - usa drive_list para verlo]",
        }

    r = httpx.get(f"{BASE}/files/{fid}", headers=headers(), params={"alt": "media"}, timeout=TIMEOUT)
    _check(r, "drive_read (media)")
    text = r.text
    return {**info, "truncated": len(text) > TEXT_LIMIT, "content": text[:TEXT_LIMIT]}


def drive_search(name: str) -> dict:
    q = f"name contains '{escape_drive_query(name)}' and trashed=false"
    r = httpx.get(
        f"{BASE}/files",
        headers=headers(),
        params={"q": q, "fields": "files(id,name,mimeType)"},
        timeout=TIMEOUT,
    )
    _check(r, "drive_search")
    return {"files": r.json().get("files", []), "query": q}

