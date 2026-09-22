import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY","")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID","")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET","")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN","")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_DEFAULT_CHANNEL_ID = os.getenv("DISCORD_DEFAULT_CHANNEL_ID", "")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Invariante del grande portada: capacidades que siempre piden confirmacion
INVARIANT_APPROVAL = {"send", "delete", "publish", "remove", "refund", "payment"}
def requires_approval(capability: str) -> bool:
    cap = (capability or "").lower()
    return any(seg in cap for seg in INVARIANT_APPROVAL)
