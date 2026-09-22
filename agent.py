"""Orquestador del agente: habla con Gemini, ejecuta tools y mantiene memoria."""
import logging
import threading

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, TOOL_EFFECTS, needs_approval
from memory import MemoryStore, WorkingMemory
from tools import ALL_SCHEMAS, BASE_HANDLERS

logger = logging.getLogger("mini_agent.agent")

MAX_STEPS_DEFAULT = 8

_client = None
_client_lock = threading.Lock()


def _get_client():
    """Cliente de Gemini perezoso (no se crea al importar el modulo)."""
    global _client
    if _client is None and GEMINI_API_KEY:
        with _client_lock:
            if _client is None and GEMINI_API_KEY:
                _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _system_prompt(store: MemoryStore) -> str:
    facts_meta = store.semantic_all_with_meta()
    sops = store.procedural_all_meta()
    goals = store.goal_list()
    recent = store.episodic_recent(6)
    lines = [
        "Eres Mini-Agent personal. Operas Gmail, Drive, Calendar, Discord y busqueda web gratis.",
        "Reglas duras:",
        "- Usa tools cuando toque. No inventes IDs.",
        "- Antes de gmail_send/discord_send/calendar_create con invitados, explica que vas a hacer",
        "  y espera confirmacion del usuario en este mismo turno.",
        "- Responde breve, en idioma del usuario.",
        "- Guarda hechos durables con remember_fact (confidence alta si el usuario lo dice directo).",
        "- Guarda objetivos con add_goal cuando el usuario diga un objetivo.",
        "- Guarda SOPs con save_sop cuando diga 'a partir de ahora cuando...'.",
        "",
    ]
    if facts_meta:
        lines.append("Hechos conocidos (con confianza):")
        for k, v in facts_meta.items():
            conf = float(v.get("confidence", 1.0))
            if conf < 0.4:
                continue
            lines.append(
                f"  - {k}: {v.get('value')} (conf {conf:.2f}, fuente {v.get('source') or 'n/d'})"
            )
        lines.append("")
    if goals:
        lines.append("Objetivos activos (prioridad alta primero):")
        for g in sorted(goals, key=lambda x: -x.get("priority", 0))[:5]:
            lines.append(f"  - [{g.get('priority', 50)}] {g.get('description')} [{g.get('status')}]")
        lines.append("")
    if sops:
        lines.append("SOPs guardados:")
        for name, meta in sops.items():
            lines.append(
                f"  - {name} v{meta.get('version', 1)}: {meta.get('description', '')} "
                f"-> {len(meta.get('steps', []))} pasos"
            )
        lines.append("")
    if recent:
        lines.append("Actividad reciente:")
        for event in recent:
            payload = event.get("payload", {}) or {}
            summary = payload.get("text") or payload.get("tool") or payload.get("error") or ""
            lines.append(f"  - {event.get('type')}: {str(summary)[:120]}")
        lines.append("")
    return "\n".join(lines)


def _build_tool() -> types.Tool:
    return types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name=s["name"], description=s["description"], parameters=s["parameters"]
        )
        for s in ALL_SCHEMAS
    ])


def _to_contents(working: WorkingMemory):
    contents = []
    for m in working.all():
        role = "user" if m["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    return contents


def _safe_args(args: dict) -> dict:
    return {k: str(v)[:80] for k, v in (args or {}).items()}


def _handlers_for(store: MemoryStore) -> dict:
    def remember_fact(key: str, value: str, confidence: float = 1.0):
        # Devuelve el resultado real: si se descarta por menor confianza, el
        # modelo lo sabe en vez de recibir un ok falso.
        return store.semantic_set(key, value, confidence=confidence, source="llm")

    def recall_facts(query: str = ""):
        return {"facts": store.semantic_search(query)}

    def save_sop(name: str, steps: list, description: str = ""):
        return store.procedural_set(name, steps, description=description)

    def list_sops():
        return {"sops": store.procedural_all_meta()}

    def add_goal(description: str, priority: int = 50):
        return store.goal_add(description, priority)

    def list_goals():
        return {"goals": store.goal_list()}

    return {
        **BASE_HANDLERS,
        "remember_fact": remember_fact,
        "recall_facts": recall_facts,
        "save_sop": save_sop,
        "list_sops": list_sops,
        "add_goal": add_goal,
        "list_goals": list_goals,
    }


def run_tool(name: str, args: dict | None, handlers: dict, store: MemoryStore, safe_mode: bool = True) -> dict:
    """Punto unico de ejecucion de tools.

    - aplica la invariante de aprobacion (arg-aware) antes de ejecutar nada,
    - registra en la memoria episodica tambien los bloqueos, las tools
      desconocidas y los errores (antes solo se registraba el camino feliz).
    """
    args = args or {}

    handler = handlers.get(name)
    if handler is None:
        # se comprueba antes de la aprobacion: una tool inexistente no "pide
        # confirmacion", simplemente no existe
        store.episodic_add("tool_unknown", {"tool": name, "args": _safe_args(args)})
        return {"error": f"tool desconocida {name}"}

    if safe_mode and needs_approval(name, args):
        effect = TOOL_EFFECTS.get(name, "unknown")
        store.episodic_add("tool_blocked", {"tool": name, "effect": effect, "args": _safe_args(args)})
        return {
            "error": (
                f"Bloqueado por modo seguro: {name} ({effect}) requiere confirmacion. "
                "Pide confirmacion al usuario y desactiva el modo seguro para ejecutarlo."
            )
        }

    try:
        result = handler(**args)
    except TypeError as e:  # argumentos que no encajan con la firma del handler
        store.episodic_add("tool_error", {"tool": name, "error": f"TypeError: {e}"[:300]})
        return {"error": f"argumentos invalidos para {name}: {e}"}
    except Exception as e:  # noqa: BLE001 - frontera con APIs externas
        logger.warning("tool %s fallo: %s", name, e)
        store.episodic_add("tool_error", {"tool": name, "error": str(e)[:300]})
        return {"error": str(e)[:500]}

    if not isinstance(result, dict):
        result = {"result": result}
    store.episodic_add("tool_call", {"tool": name, "ok": "error" not in result, "args": _safe_args(args)})
    return result


def chat(
    user_message: str,
    working: WorkingMemory,
    store: MemoryStore,
    max_steps: int = MAX_STEPS_DEFAULT,
    safe_mode: bool = True,
) -> str:
    """Ejecuta un turno de conversacion.

    `safe_mode` es True por defecto (fail safe): el modo inseguro hay que pedirlo
    explicitamente, no al contrario.
    """
    client = _get_client()
    if client is None:
        return "Falta GEMINI_API_KEY en .env"

    store.episodic_add("user_message", {"text": (user_message or "")[:300]})
    contents = _to_contents(working)
    # Si quien llama no ha metido el mensaje en la memoria de trabajo, se añade
    # aqui para no perder el turno actual.
    if not contents or contents[-1].role != "user":
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    handlers = _handlers_for(store)
    tools = [_build_tool()]
    last_text = ""
    steps = max(1, int(max_steps))

    for step in range(steps):
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(tools=tools, system_instruction=_system_prompt(store)),
        )
        candidates = response.candidates or []
        content = candidates[0].content if candidates else None
        if content is None:
            return last_text or "Sin respuesta del modelo"

        text = response.text or ""
        if text:
            last_text = text
        contents.append(content)

        calls = [p.function_call for p in (content.parts or []) if getattr(p, "function_call", None)]
        if not calls:
            store.episodic_add("assistant_message", {"text": text[:300]})
            return text

        fr_parts = []
        for fc in calls:
            args = dict(fc.args) if fc.args else {}
            result = run_tool(fc.name, args, handlers, store, safe_mode=safe_mode)
            fr_parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
        contents.append(types.Content(role="user", parts=fr_parts))
        logger.info("paso %s/%s: %s tool call(s)", step + 1, steps, len(calls))

    # Presupuesto de pasos agotado: no se descarta lo que el modelo ya dijo.
    note = f"[Se alcanzo el maximo de {steps} pasos sin respuesta final; revisa el ultimo resultado]"
    store.episodic_add("assistant_message", {"text": note})
    return f"{last_text}\n\n{note}" if last_text else note

