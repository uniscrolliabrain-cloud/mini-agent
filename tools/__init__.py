from .gmail import gmail_list, gmail_send, gmail_create_draft
from .drive import drive_list, drive_read, drive_search
from .calendar import calendar_list, calendar_create
from .discord import discord_send, discord_read
from .search import web_search, email_search

BASE_HANDLERS = {
    "gmail_list": gmail_list,
    "gmail_send": gmail_send,
    "gmail_create_draft": gmail_create_draft,
    "drive_list": drive_list,
    "drive_read": drive_read,
    "drive_search": drive_search,
    "calendar_list": calendar_list,
    "calendar_create": calendar_create,
    "discord_send": discord_send,
    "discord_read": discord_read,
    "web_search": web_search,
    "email_search": email_search,
}

BASE_SCHEMAS = [
    {"name": "gmail_list", "description": "Lista ultimos emails. Query estilo Gmail ('is:unread', 'from:ana@x.com').",
     "parameters": {"type": "object", "properties": {"max_results": {"type": "integer"}, "query": {"type": "string"}}}},
    {"name": "gmail_send", "description": "Envia un email. REQUIERE CONFIRMACION HUMANA implicita - el sistema pide confirmar antes.",
     "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}},
    {"name": "gmail_create_draft", "description": "Crea un borrador sin enviarlo.",
     "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "subject", "body"]}},
    {"name": "drive_list", "description": "Lista archivos de Drive.",
     "parameters": {"type": "object", "properties": {"folder_id": {"type": "string"}}}},
    {"name": "drive_read", "description": "Lee un archivo de Drive por ID. Detecta si es texto.",
     "parameters": {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}},
    {"name": "drive_search", "description": "Busca archivos de Drive por nombre.",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "calendar_list", "description": "Lista proximos eventos del calendario.",
     "parameters": {"type": "object", "properties": {"max_results": {"type": "integer"}}}},
    {"name": "calendar_create", "description": "Crea un evento. start/end ISO 8601 con timezone.",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"}, "attendees": {"type": "array", "items": {"type": "string"}}}, "required": ["title", "start"]}},
    {"name": "discord_send", "description": "Envia mensaje a Discord. Requiere confirmacion si es externo.",
     "parameters": {"type": "object", "properties": {"content": {"type": "string"}, "channel_id": {"type": "string"}}, "required": ["content"]}},
    {"name": "discord_read", "description": "Lee ultimos mensajes de canal Discord.",
     "parameters": {"type": "object", "properties": {"channel_id": {"type": "string"}, "limit": {"type": "integer"}}}},
    {"name": "web_search", "description": "Busqueda web gratis via DuckDuckGo (sin API key). Para buscar info publica, docs, etc.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]}},
    {"name": "email_search", "description": "Busca emails y web a la vez. Usa gmail_list + web_search combinado para encontrar contacto + info.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]

MEMORY_SCHEMAS = [
    {"name": "remember_fact", "description": "Guarda hecho durable sobre usuario (nombre, preferencias, email habitual). confidence 0-1",
     "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}, "confidence": {"type": "number"}}, "required": ["key", "value"]}},
    {"name": "recall_facts", "description": "Busca hechos guardados. Query vacio devuelve todos.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}},
    {"name": "save_sop", "description": "Guarda procedimiento reutilizable con nombre, descripcion y pasos (lista dicts con tool+desc).", "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "steps": {"type": "array", "items": {"type": "object"}}}, "required": ["name", "steps"]}},
    {"name": "list_sops", "description": "Lista procedimientos guardados.", "parameters": {"type": "object", "properties": {}}},
    {"name": "add_goal", "description": "Añade objetivo activo del usuario con prioridad. Ej: 'lanzar agencia en septiembre' prioridad 90", "parameters": {"type": "object", "properties": {"description": {"type": "string"}, "priority": {"type": "integer"}}, "required": ["description"]}},
    {"name": "list_goals", "description": "Lista objetivos activos.", "parameters": {"type": "object", "properties": {}}},
]

ALL_SCHEMAS = BASE_SCHEMAS + MEMORY_SCHEMAS
