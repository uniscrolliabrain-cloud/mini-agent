"""Memoria 4 capas + ideas del repo grande: confidence, goals, episodic jsonl."""
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from threading import RLock

from config import DATA_DIR, USER_ID_PATTERN

logger = logging.getLogger("mini_agent.memory")

_USER_RE = re.compile(USER_ID_PATTERN)
EPISODIC_MEMORY_LIMIT = 300  # entradas que se guardan dentro de memory.json
EPISODIC_FILE_MAX_BYTES = 5 * 1024 * 1024  # rotacion del log append-only


class InvalidUserId(ValueError):
    """user_id que no cumple USER_ID_PATTERN o que resuelve fuera de DATA_DIR."""


def safe_user_dir(user_id: str) -> Path:
    """Devuelve data/<user_id> validando el identificador (anti path traversal).

    Evita que valores como '..', '../..', 'a/b' o 'C:/x' escriban fuera de DATA_DIR.
    """
    candidate = (user_id or "").strip()
    if not _USER_RE.fullmatch(candidate):
        raise InvalidUserId(f"user_id invalido: {user_id!r}")
    base = (DATA_DIR / candidate).resolve()
    if base == DATA_DIR or DATA_DIR not in base.parents:
        raise InvalidUserId(f"user_id fuera de data/: {user_id!r}")
    return base


class WorkingMemory:
    def __init__(self, cap: int = 20):
        self.cap = cap
        self.items: list[dict] = []
        self._lock = RLock()

    def add(self, role: str, content: str, meta=None):
        with self._lock:
            self.items.append({"role": role, "content": content, "at": time.time(), "meta": meta or {}})
            if len(self.items) > self.cap:
                self.items = self.items[-self.cap:]

    def all(self):
        with self._lock:
            return list(self.items)

    def clear(self):
        with self._lock:
            self.items = []


class MemoryStore:
    def __init__(self, user_id: str = "default"):
        if not isinstance(user_id, str):
            raise InvalidUserId(f"user_id debe ser str, recibido {type(user_id).__name__}")
        self.user_id = user_id
        self.base = safe_user_dir(user_id)  # lanza InvalidUserId si no es valido
        self.base.mkdir(parents=True, exist_ok=True)
        self.json_path = self.base / "memory.json"
        self.backup_path = self.base / "memory.backup.json"
        self.episodic_path = self.base / "episodic.jsonl"
        self._lock = RLock()
        self._data = self._load()

    # ---------------------------------------------------------------- persistencia
    @staticmethod
    def _empty() -> dict:
        return {"episodic": [], "semantic": {}, "procedural": {}, "goals": []}

    def _load(self) -> dict:
        if not self.json_path.exists():
            return self._empty()
        try:
            data = json.loads(self.json_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("memory.json no contiene un objeto JSON")
        except (OSError, ValueError) as e:
            # Nunca perder la memoria en silencio: se intenta el backup y, si no
            # hay, se falla de forma explicita en vez de devolver una memoria vacia.
            logger.error("memory.json ilegible (%s): %s", self.json_path, e)
            data = self._recover_from_backup(e)
        for key, default in self._empty().items():
            data.setdefault(key, default)
        return data

    def _recover_from_backup(self, original_error: Exception) -> dict:
        if self.backup_path.exists():
            try:
                data = json.loads(self.backup_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    logger.warning("memoria recuperada desde %s", self.backup_path.name)
                    return data
            except (OSError, ValueError) as e:
                logger.error("backup tambien ilegible: %s", e)
        raise RuntimeError(
            f"memory.json corrupto en {self.json_path} y sin backup valido: {original_error}"
        ) from original_error

    def _save(self):
        """Escritura atomica + backup del estado anterior."""
        with self._lock:
            payload = json.dumps(self._data, ensure_ascii=False, indent=2)
            self.base.mkdir(parents=True, exist_ok=True)  # el directorio puede faltar
            tmp = self.json_path.with_suffix(".json.tmp")
            tmp.write_text(payload, encoding="utf-8")
            if self.json_path.exists():
                shutil.copyfile(self.json_path, self.backup_path)
            os.replace(tmp, self.json_path)

    def _append_episodic_file(self, obj: dict):
        with self._lock:
            self._rotate_episodic_if_needed()
            with self.episodic_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def _rotate_episodic_if_needed(self):
        try:
            if self.episodic_path.exists() and self.episodic_path.stat().st_size > EPISODIC_FILE_MAX_BYTES:
                os.replace(self.episodic_path, self.base / "episodic.1.jsonl")
        except OSError as e:  # la rotacion no debe romper la conversacion
            logger.warning("no se pudo rotar episodic.jsonl: %s", e)

    # episodic - append-only real
    def episodic_add(self, event_type: str, payload: dict):
        entry = {"type": event_type, "payload": payload, "at": time.time()}
        with self._lock:
            self._data["episodic"].append(entry)
            self._data["episodic"] = self._data["episodic"][-EPISODIC_MEMORY_LIMIT:]
            self._save()
            self._append_episodic_file(entry)

    def episodic_recent(self, n=10): return self._data["episodic"][-n:]


    # semantic con confidence (idea del repo grande)
    def semantic_set(self, key: str, value, confidence: float = 1.0, source: str = "") -> dict:
        """Guarda un hecho. Devuelve el resultado real de la operacion.

        Reglas: el usuario manda sobre el LLM, y un valor nuevo con mucha menos
        confianza no pisa uno ya establecido. Los descartes se comunican en vez de
        fingir exito (antes devolvia None y `remember_fact` respondia ok=True).
        """
        with self._lock:
            k = (key or "").strip()
            if not k:
                return {"ok": False, "reason": "key vacia"}
            try:
                new_conf = float(confidence)
            except (TypeError, ValueError):
                return {"ok": False, "reason": f"confidence invalida: {confidence!r}"}
            existing = self._data["semantic"].get(k)
            if existing:
                old_conf = float(existing.get("confidence", 1.0))
                old_source = existing.get("source", "")
                user_wins = source != "usuario" and old_source == "usuario"
                conf_wins = source != "usuario" and old_conf > new_conf + 0.2
                if user_wins or conf_wins:
                    reason = "dato del usuario" if user_wins else f"menor confianza que {old_conf}"
                    logger.info("semantic_set descartado para %r (%s)", k, reason)
                    return {"ok": False, "reason": reason, "kept": existing}

            self._data["semantic"][k] = {
                "value": value,
                "confidence": new_conf,
                "source": source,
                "at": time.time(),
            }
            self._save()
            return {"ok": True, "key": k, "confidence": new_conf, "replaced": bool(existing)}

    def semantic_get(self, key: str):
        e = self._data["semantic"].get(key)
        return e["value"] if e else None

    def semantic_all(self): return {k: v["value"] for k, v in self._data["semantic"].items()}
    def semantic_all_with_meta(self): return self._data["semantic"]

    def semantic_search(self, query: str = ""):
        q = (query or "").lower()
        if not q: return self.semantic_all()
        out = {}
        for k, v in self._data["semantic"].items():
            if q in k.lower() or q in str(v.get("value", "")).lower():
                # filtrar baja confianza
                if v.get("confidence", 1.0) < 0.35: continue
                out[k] = v["value"]
        return out

    # procedural versionado
    def procedural_set(self, name: str, steps: list, description: str = "") -> dict:
        with self._lock:
            name = (name or "").strip()
            if not name:
                return {"ok": False, "reason": "name vacio"}
            existing = self._data["procedural"].get(name, {})
            ver = existing.get("version", 0) + 1
            self._data["procedural"][name] = {
                "steps": steps,
                "description": description,
                "version": ver,
                "at": time.time(),
            }
            self._save()
            return {"ok": True, "name": name, "version": ver}

    def procedural_get(self, name: str):
        e = self._data["procedural"].get(name)
        return e["steps"] if e else None
    def procedural_all(self): return {k: v["steps"] for k, v in self._data["procedural"].items()}
    def procedural_all_meta(self): return self._data["procedural"]

    # goals (idea repo grande - GoalStack simplificado)
    def goal_add(self, description: str, priority: int = 50) -> dict:
        with self._lock:
            description = (description or "").strip()
            if not description:
                return {"ok": False, "reason": "description vacia"}
            try:
                priority = int(priority)
            except (TypeError, ValueError):
                priority = 50
            self._data["goals"].append({
                "description": description,
                "priority": priority,
                "at": time.time(),
                "status": "active",
            })
            self._data["goals"] = sorted(self._data["goals"], key=lambda g: -g["priority"])[-20:]
            self._save()
            return {"ok": True, "description": description, "priority": priority}
    def goal_list(self): return self._data["goals"]
    def goal_top(self): return self._data["goals"][0] if self._data["goals"] else None

    def snapshot(self):
        return {
            "user_id": self.user_id,
            "semantic": self.semantic_all(),
            "semantic_meta": self.semantic_all_with_meta(),
            "procedural": self.procedural_all(),
            "procedural_meta": self.procedural_all_meta(),
            "goals": self.goal_list(),
            "episodic_recent": self.episodic_recent(10),
        }

    def clear(self):
        """Borra la memoria del usuario (datos, backup y log episodico)."""
        with self._lock:
            self._data = self._empty()
            self._save()
            for path in (self.episodic_path, self.base / "episodic.1.jsonl"):
                try:
                    path.unlink(missing_ok=True)
                except OSError as e:
                    logger.warning("no se pudo borrar %s: %s", path, e)

