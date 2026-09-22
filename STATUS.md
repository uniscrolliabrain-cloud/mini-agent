# Status del repo

## Estado de los fixes

El [AUDIT.md](AUDIT.md) describe el estado pre-fixes del commit `a9a2db7`
("feat: mini-agent"). Los fixes auditados se aplicaron en `149b0e0`
("fix: limpia 26 fallos + docker + tests + audit").

### Fixes auditados (commit `149b0e0`)

Ver tabla de estado en la cabecera de `AUDIT.md`. Resumen rápido:

| # | Hallazgo | Estado |
|---|---|---|
| C-1 | Path traversal `user_id` | ✅ fix (`safe_user_dir` regex + `resolve()`) |
| C-2 | API sin auth / CORS `*` | ✅ fix (`require_api_key` 503 fail-closed) |
| A-1 | `web_search` 0 resultados | ✅ fix (`ddgs`, error explícito en vacío) |
| A-2 | `safe_mode=False` / aprobación | ✅ fix (`safe_mode=True`, `TOOL_EFFECTS`) |
| A-3 | `memory.json` corrupto | ✅ fix (`os.replace` + backup + recovery) |
| A-4 | Calendar date/dateTime/timeZone | ✅ fix (`_event_time`) |
| A-5 | Drive export Sheets/Slides | ✅ fix (`EXPORT_MIME` + `files/export`) |
| B-2 | `package-lock.json` no versionado | ✅ fix (versionado en `149b0e0`) |

### Endurecimiento posterior (este commit)

| Bug | Descripción | Estado |
|---|---|---|
| Bug 1 | `google_auth._load_cache()` definida pero nunca llamada → refresco forzado en cada arranque | ✅ fix (`_cache = _load_cache()`) |
| Bug 2 | `memory.py` getters devuelven referencias internas → corrupción de RAM | ✅ fix (`dict()` / `list()` en 3 getters) |
| Bug 4 | `_system_prompt()` se reconstruye en cada paso del loop | ✅ fix (movido fuera del `for`) |
| Bug 3 | `frontend/package-lock.json` no versionado → CI rota | ✅ ya estaba resuelto (verificado en `149b0e0`) |

### Bug menores documentados (no bloquean despliegue)

- `Dockerfile` instala `streamlit` pero `CMD` es `uvicorn` → ~150MB de deps extra.
- `config.py` usa `load_dotenv()` sin `override=True` → variable de entorno puede enmascarar `.env`.
- `api.get_store()` mantiene `_lock` durante `MemoryStore()` (I/O). No afecta con pocos usuarios.
- `Dockerfile` sin lockfile de Python → no bit-reproducible. Usa `uv` o `pip-tools` para producción.
- B-5 parcial: `dict(fc.args)` con `None` y `max_steps` puede perder respuesta. Revisar en próxima iteración.
