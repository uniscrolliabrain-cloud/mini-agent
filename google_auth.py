import time, json
from pathlib import Path
import httpx
from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN, DATA_DIR

_cache_path = DATA_DIR / "_google_token.json"

def _load_cache():
    if _cache_path.exists():
        try:
            return json.loads(_cache_path.read_text())
        except: pass
    return {"token": None, "expires_at": 0}

def _save_cache(token, expires_at):
    try:
        _cache_path.write_text(json.dumps({"token": token, "expires_at": expires_at}))
    except: pass

_cache = _load_cache()

def access_token() -> str:
    global _cache
    now = time.time()
    if _cache.get("token") and now < _cache.get("expires_at",0) - 60:
        return _cache["token"]
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN):
        raise RuntimeError("Faltan GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN en .env")
    r = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    r.raise_for_status()
    d = r.json()
    _cache = {"token": d["access_token"], "expires_at": now + d.get("expires_in",3600)}
    _save_cache(_cache["token"], _cache["expires_at"])
    return _cache["token"]

def headers() -> dict:
    return {"Authorization": f"Bearer {access_token()}"}
