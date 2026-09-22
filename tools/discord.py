import httpx
from config import DISCORD_BOT_TOKEN, DISCORD_DEFAULT_CHANNEL_ID
BASE = "https://discord.com/api/v10"
def _channel(cid: str) -> str: return cid or DISCORD_DEFAULT_CHANNEL_ID
def discord_send(content: str, channel_id: str = "") -> dict:
    if not DISCORD_BOT_TOKEN: return {"error": "DISCORD_BOT_TOKEN no configurado"}
    cid=_channel(channel_id)
    if not cid: return {"error": "channel_id no especificado"}
    r = httpx.post(f"{BASE}/channels/{cid}/messages", headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}, json={"content": content[:1800]}, timeout=30)
    r.raise_for_status()
    return {"id": r.json()["id"], "status": "sent"}
def discord_read(channel_id: str = "", limit: int = 10) -> dict:
    if not DISCORD_BOT_TOKEN: return {"error": "DISCORD_BOT_TOKEN no configurado"}
    cid=_channel(channel_id)
    if not cid: return {"error": "channel_id no especificado"}
    r = httpx.get(f"{BASE}/channels/{cid}/messages", headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}, params={"limit": limit}, timeout=30)
    r.raise_for_status()
    return {"messages": [{"id": m["id"], "author": m["author"]["username"], "content": m["content"]} for m in r.json()]}
