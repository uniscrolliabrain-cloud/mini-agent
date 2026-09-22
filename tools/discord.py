"""Discord API: enviar y leer mensajes."""
import httpx

from config import DISCORD_BOT_TOKEN, DISCORD_DEFAULT_CHANNEL_ID

from ._util import clamp_int

BASE = "https://discord.com/api/v10"
TIMEOUT = 30
MAX_CONTENT = 1800  # limite de Discord para el contenido de un mensaje
TRUNCATED_SUFFIX = "\n[...]"
MAX_FETCH = 100  # limite de la API al leer mensajes


def _headers() -> dict:
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN no configurado")
    return {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}


def _channel(cid: str = "") -> str:
    resolved = cid or DISCORD_DEFAULT_CHANNEL_ID
    if not resolved:
        raise RuntimeError("channel_id no especificado y DISCORD_DEFAULT_CHANNEL_ID vacio")
    return resolved


def _check(r: httpx.Response, action: str) -> None:
    if r.status_code == 429:
        raise RuntimeError(
            f"{action}: rate limit de Discord, reintenta en {r.headers.get('retry-after', '?')}s"
        )
    if r.status_code >= 400:
        raise RuntimeError(f"{action} fallo ({r.status_code}): {r.text[:300]}")


def discord_send(content: str, channel_id: str = "") -> dict:
    text = (content or "").strip()
    if not text:
        return {"error": "content vacio"}
    truncated = len(text) > MAX_CONTENT
    if truncated:
        text = text[: MAX_CONTENT - len(TRUNCATED_SUFFIX)] + TRUNCATED_SUFFIX
    r = httpx.post(
        f"{BASE}/channels/{_channel(channel_id)}/messages",
        headers=_headers(),
        json={"content": text},
        timeout=TIMEOUT,
    )
    _check(r, "discord_send")
    return {
        "id": r.json().get("id", ""),
        "status": "sent",
        "truncated": truncated,
        "chars_sent": len(text),
    }


def discord_read(channel_id: str = "", limit: int = 10) -> dict:
    params = {"limit": clamp_int(limit, 10, 1, MAX_FETCH)}
    r = httpx.get(
        f"{BASE}/channels/{_channel(channel_id)}/messages",
        headers=_headers(),
        params=params,
        timeout=TIMEOUT,
    )
    _check(r, "discord_read")
    return {
        "messages": [
            {
                "id": m.get("id", ""),
                "author": m.get("author", {}).get("username", ""),
                "content": m.get("content", ""),
            }
            for m in r.json()
        ]
    }

