"""Access token de Google: refresh con cache en disco y bloqueo entre hilos."""
import json
import logging
import threading
import time

import httpx

from config import DATA_DIR, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN

logger = logging.getLogger("mini_agent.google_auth")

TOKEN_URL = "https://oauth2.googleapis.com/token"
CACHE_PATH = DATA_DIR / "_google_token.json"
_EXPIRY_MARGIN = 60  # segundos de margen antes de considerar el token caducado

_refresh_lock = threading.Lock()
_cache = {"token": None, "expires_at": 0}


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError) as e:
            logger.warning("cache de token ilegible (%s), se renovara", e)
    return {"token": None, "expires_at": 0}


def _save_cache(token: str, expires_at: float) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"token": token, "expires_at": expires_at}), encoding="utf-8"
        )
    except OSError as e:
        # la cache es solo una optimizacion: no debe romper la peticion
        logger.warning("no se pudo guardar la cache de token: %s", e)


def _is_valid(cache: dict) -> bool:
    return bool(cache.get("token")) and time.time() < cache.get("expires_at", 0) - _EXPIRY_MARGIN


def _fetch_token() -> dict:
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REFRESH_TOKEN):
        raise RuntimeError("Faltan GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN en .env")
    r = httpx.post(
        TOKEN_URL,
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if r.status_code >= 400:
        # el cuerpo de Google explica el motivo (invalid_grant, invalid_client...)
        raise RuntimeError(f"refresh de Google fallo ({r.status_code}): {r.text[:300]}")
    data = r.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"respuesta de Google sin access_token: {str(data)[:200]}")
    return {"token": token, "expires_at": time.time() + float(data.get("expires_in", 3600))}


def access_token() -> str:
    """Devuelve un access token valido, renovandolo si hace falta."""
    global _cache
    if _is_valid(_cache):
        return _cache["token"]
    with _refresh_lock:  # evita refrescos simultaneos desde varios hilos
        if _is_valid(_cache):
            return _cache["token"]  # otro hilo ya lo renovo mientras esperabamos
        _cache = _fetch_token()
        _save_cache(_cache["token"], _cache["expires_at"])
        return _cache["token"]


def headers() -> dict:
    return {"Authorization": f"Bearer {access_token()}"}

