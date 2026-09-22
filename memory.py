"""Memoria 4 capas + ideas del repo grande: confidence, goals, episodic jsonl"""
import json, time
from pathlib import Path
from threading import RLock
from config import DATA_DIR

_LOCK = RLock()

class WorkingMemory:
    def __init__(self, cap: int = 20):
        self.cap = cap
        self.items: list[dict] = []
    def add(self, role: str, content: str, meta=None):
        self.items.append({"role": role, "content": content, "at": time.time(), "meta": meta or {}})
        if len(self.items) > self.cap:
            self.items = self.items[-self.cap:]
    def all(self): return list(self.items)
    def clear(self): self.items = []

class MemoryStore:
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.base = DATA_DIR / user_id
        self.base.mkdir(parents=True, exist_ok=True)
        self.json_path = self.base / "memory.json"
        self.episodic_path = self.base / "episodic.jsonl"
        self._data = self._load()

    def _load(self):
        if not self.json_path.exists():
            return {"episodic": [], "semantic": {}, "procedural": {}, "goals": []}
        try:
            d = json.loads(self.json_path.read_text(encoding="utf-8"))
            # migracion
            d.setdefault("semantic", {})
            d.setdefault("procedural", {})
            d.setdefault("goals", [])
            d.setdefault("episodic", [])
            return d
        except Exception:
            return {"episodic": [], "semantic": {}, "procedural": {}, "goals": []}

    def _save(self):
        with _LOCK:
            self.json_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _append_episodic_file(self, obj):
        with _LOCK:
            with self.episodic_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    # episodic - append-only real
    def episodic_add(self, event_type: str, payload: dict):
        entry = {"type": event_type, "payload": payload, "at": time.time()}
        self._data["episodic"].append(entry)
        self._data["episodic"] = self._data["episodic"][-300:]
        self._save()
        self._append_episodic_file(entry)

    def episodic_recent(self, n=10): return self._data["episodic"][-n:]

    # semantic con confidence (idea del repo grande)
    def semantic_set(self, key: str, value, confidence: float = 1.0, source: str = ""):
        with _LOCK:
            k = key.strip()
            existing = self._data["semantic"].get(k)
            # no sobreescribir si nuevo tiene menos confianza y ya existe con alta
            if existing and existing.get("confidence",1.0) > confidence + 0.2:
                # mantener viejo pero actualizar si source es usuario directo
                if confidence < 0.9:
                    return
            self._data["semantic"][k] = {"value": value, "confidence": confidence, "source": source, "at": time.time()}
            self._save()

    def semantic_get(self, key: str):
        e = self._data["semantic"].get(key)
        return e["value"] if e else None

    def semantic_all(self): return {k: v["value"] for k,v in self._data["semantic"].items()}
    def semantic_all_with_meta(self): return self._data["semantic"]

    def semantic_search(self, query: str = ""):
        q = (query or "").lower()
        if not q: return self.semantic_all()
        out={}
        for k,v in self._data["semantic"].items():
            if q in k.lower() or q in str(v.get("value","")).lower():
                # filtrar baja confianza
                if v.get("confidence",1.0) < 0.35: continue
                out[k]=v["value"]
        return out

    # procedural versionado
    def procedural_set(self, name: str, steps: list, description: str = ""):
        with _LOCK:
            existing = self._data["procedural"].get(name, {})
            ver = existing.get("version",0)+1
            self._data["procedural"][name] = {"steps": steps, "description": description, "version": ver, "at": time.time()}
            self._save()

    def procedural_get(self, name: str): 
        e = self._data["procedural"].get(name)
        return e["steps"] if e else None
    def procedural_all(self): return {k: v["steps"] for k,v in self._data["procedural"].items()}
    def procedural_all_meta(self): return self._data["procedural"]

    # goals (idea repo grande - GoalStack simplificado)
    def goal_add(self, description: str, priority: int = 50):
        with _LOCK:
            self._data["goals"].append({"description": description, "priority": priority, "at": time.time(), "status": "active"})
            self._data["goals"] = sorted(self._data["goals"], key=lambda g: -g["priority"])[-20:]
            self._save()
    def goal_list(self): return self._data["goals"]
    def goal_top(self): return self._data["goals"][0] if self._data["goals"] else None

    def snapshot(self):
        return {
            "semantic": self.semantic_all(),
            "semantic_meta": self.semantic_all_with_meta(),
            "procedural": self.procedural_all(),
            "procedural_meta": self.procedural_all_meta(),
            "goals": self.goal_list(),
            "episodic_recent": self.episodic_recent(10),
        }
    def clear(self):
        with _LOCK:
            self._data = {"episodic": [], "semantic": {}, "procedural": {}, "goals": []}
            self._save()
            try: self.episodic_path.write_text("", encoding="utf-8")
            except: pass
