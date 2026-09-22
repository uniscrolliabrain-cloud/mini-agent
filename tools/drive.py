import httpx
from google_auth import headers

BASE = "https://www.googleapis.com/drive/v3"

def drive_list(folder_id: str = "") -> dict:
    q = "trashed=false"
    if folder_id: q += f" and '{folder_id}' in parents"
    r = httpx.get(f"{BASE}/files", headers=headers(), params={"q": q, "fields": "files(id,name,mimeType,size,modifiedTime)", "pageSize": 50}, timeout=30)
    r.raise_for_status()
    return {"files": r.json().get("files", [])}

def drive_read(file_id: str) -> dict:
    meta = httpx.get(f"{BASE}/files/{file_id}", headers=headers(), params={"fields": "id,name,mimeType,size"}, timeout=30).json()
    mime = meta.get("mimeType","")
    # Solo texto
    if "google-apps" in mime or mime.startswith("text/") or mime in ["application/json","text/plain","text/markdown"]:
        # export si es doc
        if "google-apps.document" in mime:
            r = httpx.get(f"{BASE}/files/{file_id}/export", headers=headers(), params={"mimeType": "text/plain"}, timeout=30)
            r.raise_for_status()
            return {"id": meta["id"], "name": meta["name"], "mimeType": mime, "content": r.text[:15000]}
        r = httpx.get(f"{BASE}/files/{file_id}", headers=headers(), params={"alt": "media"}, timeout=30)
        r.raise_for_status()
        try:
            txt = r.text[:15000]
        except:
            txt = f"[binario {mime} - no se puede leer como texto, tamaño {meta.get('size')}]"
        return {"id": meta["id"], "name": meta["name"], "mimeType": mime, "content": txt}
    else:
        return {"id": meta["id"], "name": meta["name"], "mimeType": mime, "content": f"[archivo binario {mime} no legible como texto - usa drive_list para verlo]"}

def drive_search(name: str) -> dict:
    r = httpx.get(f"{BASE}/files", headers=headers(), params={"q": f"name contains '{name}' and trashed=false", "fields": "files(id,name,mimeType)"}, timeout=30)
    r.raise_for_status()
    return {"files": r.json().get("files", [])}
