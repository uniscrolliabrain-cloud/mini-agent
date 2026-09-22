"""Configuracion central del agente.

Todas las rutas se resuelven respecto al directorio de este fichero, de modo que
la app se comporta igual la lance quien la lance (uvicorn, streamlit, docker,
pytest) y no depende del directorio de trabajo.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("mini_agent.config")

BASE_DIR = Path(__file__).resolve().parent

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN", "")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_DEFAULT_CHANNEL_ID = os.getenv("DISCORD_DEFAULT_CHANNEL_ID", "")

# Zona horaria aplicada a eventos de Calendar sin offset explicito (RFC3339).
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Madrid")

# Clave que protege la API HTTP. En despliegue es obligatoria: si falta, la API
# responde 503 en vez de quedar abierta (fail closed).
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8501").split(",")
    if o.strip()
]

DATA_DIR = Path(os.getenv("DATA_DIR") or (BASE_DIR / "data")).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Identificadores de usuario validos: deben empezar por alfanumerico, de modo que
# ".", "..", "/", "\\", ":" y las rutas relativas quedan fuera.
USER_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"

# --------------------------------------------------------------------------
# Politica de aprobacion (invariante): efectos que siempre piden confirmacion
# --------------------------------------------------------------------------
APPROVAL_REQUIRED_EFFECTS = {
    "send_email",
    "send_message",
    "invite_attendees",
    "delete",
    "publish",
    "remove",
    "refund",
    "payment",
}

# Mapa explicito tool -> efecto. Antes se deducia con `substring` sobre el nombre
# de la tool, lo que dejaba fuera acciones con efecto externo (calendar_create).
TOOL_EFFECTS = {
    "gmail_list": "read_email",
    "gmail_send": "send_email",
    "gmail_create_draft": "write_draft",
    "drive_list": "read_drive",
    "drive_read": "read_drive",
    "drive_search": "read_drive",
    "calendar_list": "read_calendar",
    "calendar_create": "invite_attendees",
    "discord_send": "send_message",
    "discord_read": "read_discord",
    "web_search": "read_web",
    "email_search": "read_email",
    "remember_fact": "write_memory",
    "recall_facts": "read_memory",
    "save_sop": "write_memory",
    "list_sops": "read_memory",
    "add_goal": "write_memory",
    "list_goals": "read_memory",
}


def needs_approval(tool_name: str, args: dict | None = None) -> bool:
    """True si la tool requiere confirmacion humana en modo seguro.

    Es arg-aware: `calendar_create` con `attendees` invita a terceros (requiere
    aprobacion); sin `attendees` solo crea un evento propio.
    """
    args = args or {}
    effect = TOOL_EFFECTS.get(tool_name)
    if effect is None:
        return True  # tool desconocida -> conservador
    if tool_name == "calendar_create" and not args.get("attendees"):
        return False
    return effect in APPROVAL_REQUIRED_EFFECTS


def missing_config() -> list[str]:
    """Claves de entorno requeridas que faltan (para el chequeo de arranque)."""
    required = {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
        "GOOGLE_REFRESH_TOKEN": GOOGLE_REFRESH_TOKEN,
    }
    return [name for name, value in required.items() if not value]


def log_startup_status() -> list[str]:
    """Logea el estado de la configuracion. Devuelve las claves que faltan."""
    missing = missing_config()
    if missing:
        logger.warning("Configuracion incompleta, faltan: %s", ", ".join(missing))
    if os.getenv("GOOGLE_API_KEY") and GEMINI_API_KEY:
        # El SDK de google-genai prioriza GOOGLE_API_KEY si no se le pasa una
        # clave explicita; aqui si se pasa, pero conviene dejarlo registrado.
        logger.warning(
            "GOOGLE_API_KEY tambien esta definida en el entorno; el agente usa "
            "GEMINI_API_KEY del .env (ultimos 4: ...%s)",
            GEMINI_API_KEY[-4:],
        )
    if not ADMIN_API_KEY:
        logger.warning("ADMIN_API_KEY vacia: la API HTTP respondera 503 hasta configurarla")
    logger.info("DATA_DIR=%s | timezone=%s | modelo=%s", DATA_DIR, DEFAULT_TIMEZONE, GEMINI_MODEL)
    return missing

