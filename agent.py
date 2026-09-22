from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, requires_approval
from memory import MemoryStore, WorkingMemory
from tools import ALL_SCHEMAS, BASE_HANDLERS

_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def _system_prompt(store: MemoryStore) -> str:
    facts = store.semantic_all()
    facts_meta = store.semantic_all_with_meta()
    sops = store.procedural_all_meta()
    goals = store.goal_list()
    recent = store.episodic_recent(6)
    lines = [
        "Eres Mini-Agent personal. Operas Gmail, Drive, Calendar, Discord y busqueda web gratis.",
        "Reglas duras:",
        "- Usa tools cuando toque. No inventes IDs.",
        "- Antes de gmail_send/discord_send, explica que vas a hacer y espera confirmacion implicita del turno.",
        "- Responde breve, en idioma del usuario.",
        "- Guarda hechos durables con remember_fact con confidence alta si usuario lo dice directo.",
        "- Guarda objetivos con add_goal cuando usuario diga objetivo.",
        "- Guarda SOPs con save_sop cuando diga 'a partir de ahora cuando...'",
        "",
    ]
    if facts:
        lines.append("Hechos conocidos (con confianza):")
        for k,v in facts_meta.items():
            conf = v.get("confidence",1.0)
            if conf < 0.4: continue
            lines.append(f"  - {k}: {v.get('value')} (conf {conf:.2f})")
        lines.append("")
    if goals:
        lines.append("Objetivos activos (prioridad alta primero):")
        for g in sorted(goals, key=lambda x: -x.get("priority",0))[:5]:
            lines.append(f"  - [{g.get('priority',50)}] {g.get('description')} [{g.get('status')}]")
        lines.append("")
    if sops:
        lines.append("SOPs guardados:")
        for name, meta in sops.items():
            desc = meta.get("description","")
            steps = meta.get("steps",[])
            lines.append(f"  - {name} v{meta.get('version',1)}: {desc} -> {len(steps)} pasos")
        lines.append("")
    return "\n".join(lines)

def _build_tool():
    return types.Tool(function_declarations=[
        types.FunctionDeclaration(name=s["name"], description=s["description"], parameters=s["parameters"]) for s in ALL_SCHEMAS
    ])

def _handlers_for(store: MemoryStore) -> dict:
    def remember_fact(key: str, value: str, confidence: float = 1.0):
        store.semantic_set(key, value, confidence=confidence, source="llm")
        return {"ok": True, "key": key, "confidence": confidence}
    def recall_facts(query: str = ""): return {"facts": store.semantic_search(query)}
    def save_sop(name: str, steps: list, description: str = ""):
        store.procedural_set(name, steps, description=description)
        return {"ok": True, "name": name}
    def list_sops(): return {"sops": store.procedural_all_meta()}
    def add_goal(description: str, priority: int = 50):
        store.goal_add(description, priority)
        return {"ok": True}
    def list_goals(): return {"goals": store.goal_list()}
    return {**BASE_HANDLERS, "remember_fact": remember_fact, "recall_facts": recall_facts, "save_sop": save_sop, "list_sops": list_sops, "add_goal": add_goal, "list_goals": list_goals}

def _to_contents(working: WorkingMemory):
    contents=[]
    for m in working.all():
        role = "user" if m["role"]=="user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    return contents

def chat(user_message: str, working: WorkingMemory, store: MemoryStore, max_steps: int = 8, safe_mode: bool = False) -> str:
    if not _client:
        return "Falta GEMINI_API_KEY en .env"
    store.episodic_add("user_message", {"text": user_message[:300]})
    contents = _to_contents(working)
    handlers = _handlers_for(store)
    tools = [_build_tool()]
    for _ in range(max_steps):
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(tools=tools, system_instruction=_system_prompt(store))
        )
        if not response.candidates: return "Sin respuesta del modelo"
        contents.append(response.candidates[0].content)
        calls = [p.function_call for p in response.candidates[0].content.parts if getattr(p, "function_call", None)]
        if not calls:
            text = response.text or ""
            store.episodic_add("assistant_message", {"text": text[:300]})
            return text
        fr_parts=[]
        for fc in calls:
            name=fc.name
            args=dict(fc.args)
            # Bloqueo modo seguro (idea Role forbidden_tools del repo grande)
            if safe_mode and requires_approval(name):
                result={"error": f"Bloqueado por modo seguro: {name} requiere confirmacion. Desactiva modo seguro."}
            else:
                handler=handlers.get(name)
                if not handler: result={"error": f"tool desconocida {name}"}
                else:
                    try:
                        result=handler(**args)
                        store.episodic_add("tool_call", {"tool": name, "ok": "error" not in result, "args": {k: str(v)[:80] for k,v in args.items()}})
                    except Exception as e:
                        result={"error": str(e)[:500]}
                        store.episodic_add("tool_error", {"tool": name, "error": str(e)[:300]})
            fr_parts.append(types.Part.from_function_response(name=name, response={"result": result}))
        contents.append(types.Content(role="user", parts=fr_parts))
    return "Supere max pasos"
