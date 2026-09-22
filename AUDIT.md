> **AVISO:** este informe describe el estado en el commit `a9a2db7` (pre-fixes,
> "feat: mini-agent"). Los fixes se aplicaron en el commit `149b0e0`
> ("fix: limpia 26 fallos + docker + tests + audit") y en commits posteriores.
> El código de `master` **ya no está intacto**: los parches están aplicados.
> Ver tabla de estado de los hallazgos:
>
> | # | Severidad | Hallazgo | Estado | Commit |
> |---|---|---|---|---|
> | C-1 | Crítico | Path traversal: `user_id` escribe fuera de `data/` | ✅ fix | `149b0e0` |
> | C-2 | Crítico | API sin auth, CORS `*`, `/memory/{user_id}` abierto | ✅ fix | `149b0e0` |
> | A-1 | Alto | `web_search` devuelve 0 resultados en silencio | ✅ fix | `149b0e0` |
> | A-2 | Alto | `safe_mode=False` por defecto; aprobación eludible | ✅ fix | `149b0e0` |
> | A-3 | Alto | `memory.json` corrupto borra toda la memoria | ✅ fix | `149b0e0` |
> | A-4 | Alto | `calendar_create` envía cuerpos inválidos (date/dateTime/timeZone) | ✅ fix | `149b0e0` |
> | A-5 | Alto | `drive_read` no lee Sheets/Slides (usa `alt=media` en vez de export) | ✅ fix | `149b0e0` |
> | M-1 | Medio | `drive_search` inyecta nombre sin escapar | ✅ fix | `149b0e0` |
> | M-2 | Medio | LLM pisa hechos (`confidence` 1.0), no-ops como `ok` | ✅ fix | `149b0e0` |
> | M-3 | Medio | `DATA_DIR` relativo al CWD | ✅ fix | `149b0e0` |
> | M-4 | Medio | `episodic.jsonl` sin pruning + reescritura completa | ✅ fix | `149b0e0` |
> | M-5 | Medio | `GOOGLE_API_KEY` enmascara `GEMINI_API_KEY` | ✅ fix | `149b0e0` |
> | M-6 | Medio | README roto: falta `.env.example`, `DISCORD_BOT_TOKEN` | ✅ fix | `149b0e0` |
> | M-7 | Medio | Sin tests, CI, lint ni lockfile | ✅ fix | `149b0e0` |
> | B-1 | Bajo | `.gitignore` no ignora `frontend/.env*` | ✅ fix | `149b0e0` |
> | B-2 | Bajo | `frontend/package-lock.json` no versionado | ✅ fix | `149b0e0` |
> | B-3 | Bajo | Frontend: falta `r.ok`, `user_id` sin encode, proxy muerto | ✅ fix | `149b0e0` |
> | B-4 | Bajo | `api.py` dicts globales sin lock ni expiración | ✅ fix | `149b0e0` |
> | B-5 | Bajo | `agent.py`: `max_steps` pierde respuesta, `dict(fc.args)` con None | ⚠️ parcial | `149b0e0` |
> | B-6 | Bajo | Discord: truncado silencioso, `limit>100` ⇒ 400, 429 no gestionado | ✅ fix | `149b0e0` |
> | B-7 | Bajo | `tools/search.py` promete fallback que no existe | ✅ fix | `149b0e0` |
> | B-8 | Bajo | `.env` con drift (`GOOGLE_REAL` duplicada, claves muertas) | ✅ fix | `149b0e0` |
> | B-9 | Bajo | Imports sin ordenar, `bare except`, variable sin usar | ✅ fix | `149b0e0` |
> | B-10 | Bajo | `app.py` Streamlit no verificado | ✅ fix | `149b0e0` |
>
> Los bugs de endurecimiento posterior detectados tras validar el reporte se
> documentan en `STATUS.md` y se corrigen en este mismo commit.

# Auditoría técnica de `mini-agent`

- **Fecha:** 2026-09-22
- **Rama:** `audit/full-repo-audit-2026-09-22` (creada desde `master` @ `a9a2db7`)
- **Alcance:** los 21 ficheros versionados (5.4k de código: 6 módulos Python raíz, 6 tools, 5 ficheros de frontend React/Vite, README, requirements, .gitignore)
- **Autor:** revisión automatizada + verificación ejecutando el código

## 1. Resumen ejecutivo

El repo es un vertical slice funcional y legible, pero **no está listo para desplegarse**: hay 2 fallos críticos de seguridad,
5 altos que rompen funcionalidad prometida en el README, 7 medios y 10 bajos.

| # | Severidad | Hallazgo | Estado verificado |
|---|-----------|----------|-------------------|
| C-1 | Crítico | `user_id` sin sanear ⇒ se escriben ficheros fuera de `data/` (path traversal) | Reproducido |
| C-2 | Crítico | API sin autenticación, CORS `*`, `/memory/{user_id}` abierto a lectura/borrado | Reproducido |
| A-1 | Alto | `web_search` devuelve **0 resultados en silencio** (paquete `duckduckgo-search` obsoleto) | Reproducido (4 queries) |
| A-2 | Alto | Invariante de aprobación eludible: `safe_mode=False` por defecto en `agent.chat`; `calendar_create` no está cubierta | Reproducido |
| A-3 | Alto | Corrupción de `memory.json` ⇒ pérdida total y silenciosa de toda la memoria | Reproducido |
| A-4 | Alto | `calendar_create` envía cuerpos inválidos (date-only y `dateTime` sin `timeZone`) | Verificado contra el contrato de la API |
| A-5 | Alto | `drive_read` no puede leer Sheets/Slides (usa `alt=media` en vez de `files.export`) | Verificado contra la API + doc oficial |
| M-1 | Medio | `drive_search` inyecta el nombre sin escapar ⇒ query inválida | Reproducido |
| M-2 | Medio | El LLM pisa hechos del usuario (`confidence` 1.0) y los no-ops se reportan como `ok` | Reproducido |
| M-3 | Medio | `DATA_DIR` relativo al CWD ⇒ los datos acaban donde se lance el proceso | Reproducido |
| M-4 | Medio | `episodic.jsonl` sin pruning + reescritura completa del JSON en cada evento | Reproducido |
| M-5 | Medio | `GOOGLE_API_KEY` del sistema enmascara `GEMINI_API_KEY`: la app puede usar otra clave sin avisar | Reproducido |
| M-6 | Medio | Setup documentado roto: falta `.env.example`; `DISCORD_BOT_TOKEN` no existe en `.env` | Reproducido |
| M-7 | Medio | Sin tests, CI, lint config ni lockfile versionado ⇒ nada protege de regresiones | Reproducido (ruff: 30 hallazgos) |
| B-1 | Bajo | `.gitignore` no ignora `frontend/.env*` | Reproducido |
| B-2 | Bajo | `frontend/package-lock.json` generado pero sin versionar | Reproducido |
| B-3 | Bajo | Frontend: falta `r.ok`, `j.reply` puede ser `undefined`, `user_id` sin `encodeURIComponent`, proxy `/api` muerto | Por inspección |
| B-4 | Bajo | `api.py` con dicts globales sin lock ni expiración; historial compartido entre clientes | Por inspección |
| B-5 | Bajo | `agent.py`: `max_steps` pierde la respuesta, `dict(fc.args)` con `None`, eventos no registrados | Por inspección |
| B-6 | Bajo | Discord: truncado silencioso, `limit>100` ⇒ 400, sin manejo de 429 | Por inspección |
| B-7 | Bajo | `tools/search.py` promete un fallback que no existe | Reproducido |
| B-8 | Bajo | `.env` con drift del repo grande (`GOOGLE_REAL` duplicada, 8 claves muertas) | Reproducido |
| B-9 | Bajo | Calidad: 12 imports sin ordenar, 4 `bare except`, 5 `blind except`, 1 variable sin usar | Reproducido (ruff) |
| B-10 | Bajo | `app.py`: `st.checkbox(value=..., key="safe_mode")`; sin verificar (Streamlit no instalado) | No verificado |

> **AVISO (actualización):** los arreglos propuestos en este informe **ya se han aplicado**
> en el commit `149b0e0` y confirmados en este repo. El código de `master` no está intacto:
> ver la tabla de estado en la cabecera de este fichero. Los bugs de endurecimiento
> posterior (ver `STATUS.md`) se corrigen en el commit actual.

## 2. Método y entorno

| Comprobación | Herramienta | Resultado |
|---|---|---|
| Compilación de todos los `.py` | `python -m compileall` (3.12.10) | OK, 0 errores |
| Imports núcleo | `import config, memory, google_auth` | OK |
| Lint Python | `ruff check .` (sin config en el repo) | **30 errores** |
| Modelo/tools offline | `_build_tool()` con `google-genai 2.21.0` | OK, 18 declarations |
| Backend HTTP | `api.app.openapi()`, `api.get_store()` | 0 esquemas de seguridad |
| Frontend build | `npm install` + `npm run build` (node 24.18.1, vite 5.4.21) | OK en 4.19s, 32 módulos |
| Dependencias JS | `npm audit --omit=dev` | **0 vulnerabilidades** |
| Dependencias Python | `pip install --target` de `duckduckgo-search` (8.1.1) + sonda real | instalado, pero la búsqueda devuelve 0 resultados |
| Comprobaciones funcionales | script de auditoría con `httpx`/mocks (21 checks) | ver evidencias por hallazgo |
| Secretos en git | `git log --all --name-only`, `git ls-files` | `.env` nunca fue versionado (OK) |

**Limitaciones declaradas**

- No se ejecutó `app.py` (Streamlit) porque `streamlit` no está instalado en este entorno y no hay tests: **B-10 queda sin verificar**.
- No se hicieron llamadas reales a Gmail/Drive/Calendar/Discord ni a Gemini: el `.env` local contiene credenciales reales y
  no se debe tocar datos del usuario. Los fallos A-4/A-5 se han verificado contra el contrato de la API (cuerpo/URL generados + documentación oficial citada).
- Los mocks de `httpx` usados en las comprobaciones están fuera del repo (`%TEMP%\ma_audit\audit_checks.py`).

## 3. Hallazgos críticos

### C-1 · Path traversal: `user_id` escribe ficheros fuera de `data/`

- **Dónde:** `memory.py:23` (`self.base = DATA_DIR / user_id`), usado desde `api.py:13-17`, `api.py:36-45` y `app.py:18-20`.
- **Problema:** `user_id` llega del cliente (JSON de `/chat`, path param de `/memory/{user_id}`, o el `st.text_input` del sidebar)
  y se concatena tal cual a una ruta. No hay validación ni saneado.
- **Evidencia** (`MemoryStore("..")` y `api.get_store("..")`, ambos ejecutados):

  ```
  user_id='..' -> base.resolve()=C:\Users\Alfonso\Desktop\git hub repos\mini-agent
                 -> memory.json creado en la raiz del repo=True
                 -> contenido escrito: {'pwned': {'value': 'escrito fuera de data/', 'confidence': 1.0, ...}}
  GET /memory/.. -> escribe memory.json en la raiz del repo=True   (endpoint publico, sin auth)
  user_id='a/b/c' crea subdirectorios: True (data\a\b\c)
  ```
- **Impacto:** cualquier cliente puede crear/sobrescribir `memory.json`, `episodic.jsonl` y directorios arbitrarios
  (p. ej. `..\..\`) en el host, además de poder leer/escribir la memoria de esos "usuarios". En despliegue con volumen
  escribible es una escritura arbitraria de ficheros.
- **Fix propuesto:** validar y normalizar el identificador en un único sitio:

  ```python
  # memory.py
  import re
  _USER_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

  def _safe_user_dir(user_id: str) -> Path:
      if not _USER_RE.fullmatch(user_id or ""):
          raise ValueError(f"user_id invalido: {user_id!r}")
      base = (DATA_DIR / user_id).resolve()
      if DATA_DIR.resolve() not in base.parents:
          raise ValueError("user_id fuera de data/")
      return base
  ```
  Y en `api.py`/`app.py` devolver `400`/mensaje de error en vez de propagar la ruta.

### C-2 · API sin autenticación y con CORS `*`

- **Dónde:** `api.py:7-8` (`FastAPI(...)` + `CORSMiddleware(allow_origins=["*"])`), `api.py:28-45` (endpoints).
- **Evidencia:**

  ```
  securitySchemes={}
  middleware=['CORSMiddleware']
  rutas=["['GET','HEAD'] /openapi.json", "['GET','HEAD'] /docs", ...,
         "['POST'] /chat", "['GET'] /memory/{user_id}", "['DELETE'] /memory/{user_id}"]
  ```
- **Impacto:** cualquiera que alcance el puerto puede: leer la memoria de cualquier `user_id` (hechos personales, emails, objetivos),
  borrarla (`DELETE /memory/{user_id}`), y consumir la cuota de Gemini del dueño (`POST /chat`). CORS `*` permite además que
  cualquier web haga esas llamadas desde el navegador de la víctima. Combinado con C-1 es escritura de ficheros sin credenciales.
  El `.env` local ya contiene una `ADMIN_API_KEY` (28 chars) que **el código no usa en ninguna parte**.
- **Fix propuesto:** añadir una dependencia de seguridad (API key o JWT) a `/chat` y `/memory/*`, restringir `allow_origins` a
  la URL del frontend y activar `allow_credentials` sólo si hace falta:

  ```python
  from fastapi import Depends, HTTPException, Security
  from fastapi.security import APIKeyHeader
  from config import ADMIN_API_KEY

  _key = APIKeyHeader(name="X-API-Key")

  def require_key(k: str = Security(_key)):
      if not ADMIN_API_KEY or k != ADMIN_API_KEY:
          raise HTTPException(status_code=401, detail="API key invalida")
  ```

## 4. Hallazgos altos

### A-1 · `web_search` devuelve 0 resultados en silencio (funcionalidad estrella rota)

- **Dónde:** `tools/search.py:2,5-15`; pin en `requirements.txt:7` (`duckduckgo-search>=6.0`).
- **Problema:** el paquete `duckduckgo_search` está **renombrado a `ddgs`** (aviso del propio PyPI:
  _"This package (`duckduckgo_search`) has been renamed to `ddgs`! Use `pip install ddgs` instead."_).
  Con la versión 8.1.1 (la que instala ese pin) las llamadas devuelven lista vacía **sin lanzar excepción**, así que el
  `try/except` nunca rellena la clave `error` y el agente responde "no he encontrado nada" como si fuera un resultado legítimo.
- **Evidencia** (instalación real de `duckduckgo-search==8.1.1` y `web_search()` del repo):

  ```
  warning: tools/search.py:7: RuntimeWarning: This package (`duckduckgo_search`) has been renamed to `ddgs`!
  query='python 3.13 novedades' elapsed=4.2s n_results=0 keys=['query', 'results']
  query='openai'               elapsed=3.0s n_results=0 keys=['query', 'results']
  query='github'               elapsed=5.1s n_results=0 keys=['query', 'results']
  query='weather madrid'       elapsed=3.6s n_results=0 keys=['query', 'results']
  ```
- **Impacto:** `web_search`, `email_search` y el soporte de "busca en la web" del README no funcionan; el fallo es silencioso
  (ni error, ni traza, ni aviso en la UI).
- **Fix propuesto:** migrar a `ddgs` (`pip install ddgs`), cubrir todas las versiones con un rango o fijarlas, y **no** tragarse
  el fallo: si la lista viene vacía, devolver `{"error": ...}`; e implementar de verdad el fallback prometido en el comentario
  (ver B-7).

  ```python
  try:
      from ddgs import DDGS          # paquete vigente
  except ModuleNotFoundError:
      from duckduckgo_search import DDGS  # compat con instalaciones antiguas

  def web_search(query: str, max_results: int = 5) -> dict:
      try:
          with DDGS() as ddgs:
              out = [{"title": r.get("title", ""), "url": r.get("href", ""),
                      "snippet": r.get("body", "")[:300]} for r in ddgs.text(query, max_results=max_results)]
      except Exception as e:
          return {"results": [], "query": query, "error": f"{type(e).__name__}: {e}"}
      if not out:
          return {"results": [], "query": query, "error": "busqueda sin resultados o backend bloqueado"}
      return {"results": out, "query": query}
  ```

### A-2 · La invariante de aprobación es eludible y no cubre acciones con efecto externo

- **Dónde:** `agent.py:74` (`safe_mode: bool = False`), `api.py:22` (`safe_mode: bool = True`), `config.py:21-24`, `tools/calendar.py:12-14`.
- **Evidencia:**

  ```
  agent.chat safe_mode por defecto=False | api.ChatIn.safe_mode default=True
  gmail_send=True, discord_send=True, gmail_create_draft=False, calendar_create=False,
  drive_search=False, calendar_delete=True, resend_message=True, sendmail=True
  ```
- **Problemas concretos:**
  1. Dos valores por defecto contradictorios: cualquier llamada interna a `chat()` (tests, scripts, futuros workers) nace con
     el modo seguro **desactivado**, que es el caso inseguro.
  2. `requires_approval()` hace `substring` sobre el nombre de la tool: `calendar_create` **no** está cubierta aunque con
     `attendees` envía invitaciones por email a terceros (efecto externo real). También `sendmail`/`resend_message` darían
     `True` por accidente, y `delete/publish/remove/refund/payment` de `INVARIANT_APPROVAL` no corresponden a ninguna tool (política muerta).
  3. El bloqueo sólo ocurre en `chat()`; si mañana se llama a `tools.gmail.gmail_send` directamente no hay ninguna barrera.
  4. Cuando se bloquea una tool, tampoco se registra el intento en la memoria episódica (ver B-5), lo que rompe la auditabilidad.
- **Fix propuesto:** `safe_mode: bool = True` por defecto; declarar el efecto de cada tool en un registro
  (`{"gmail_send": "external_send", "calendar_create": "external_invite", ...}`) en vez de por substring; y bloquear en el
  propio handler (`gmail_send(..., _approved=False)`) para que la invariante no dependa del orquestador.

### A-3 · Un `memory.json` corrupto borra toda la memoria sin avisar

- **Dónde:** `memory.py:29-41` (`_load` con `except Exception: return {vacio}`), `memory.py:43-45` (`_save` con `write_text` no atómico).
- **Evidencia:** se escribió un `memory.json` válido (`nombre=Ana`, 1 goal), se truncó a la mitad (simulando un corte de proceso
  durante `_save`) y se recargó:

  ```
  antes: nombre=Ana + 1 goal | tras JSON truncado -> semantic={} goals=[] (pierde todo, sin aviso ni backup)
  ```
- **Impacto:** un crash/OOM/disco lleno durante cualquiera de las muchas escrituras (`semantic_set`, `goal_add`, cada
  `episodic_add` reescribe el fichero completo) destruye el contexto del usuario de forma irreversible y silenciosa.
- **Fix propuesto:** escritura atómica + backup + error explícito:

  ```python
  def _save(self):
      with _LOCK:
          tmp = self.json_path.with_suffix(".json.tmp")
          tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
          os.replace(tmp, self.json_path)          # atomico
          shutil.copyfile(self.json_path, self.json_path.with_suffix(".json.bak"))

  def _load(self):
      try:
          ...
      except Exception as e:
          backup = self.json_path.with_suffix(".json.bak")
          if backup.exists():                      # intenta recuperar
              ...
          raise RuntimeError(f"memory.json corrupto en {self.json_path}: {e}") from e
  ```

### A-4 · `calendar_create` genera cuerpos que la Calendar API rechaza

- **Dónde:** `tools/calendar.py:12-14`.
- **Evidencia** (cuerpos realmente generados por el código):

  ```
  calendar_create(title="Cita", start="2026-09-22")
    -> {"summary": "Cita", "start": {"dateTime": "2026-09-22"}, "end": {"dateTime": "2026-09-22"}}

  calendar_create(title="Cita", start="2026-09-22T10:00:00", attendees=["ana@acme.com"])
    -> {"summary": "Cita", "start": {"dateTime": "2026-09-22T10:00:00"},
        "end": {"dateTime": "2026-09-22T10:00:00"}, "attendees": [{"email": "ana@acme.com"}]}
  ```
- **Contrato oficial** (discovery doc `calendar/v3`, schema `EventDateTime`):
  - `dateTime`: _"The time, as a combined date-time value (formatted according to RFC3339). **A time zone offset is required
    unless a time zone is explicitly specified in timeZone.**"_
  - `date`: _"The date, in the format \"yyyy-mm-dd\", if this is an all-day event."_
- **Impacto:** dos casos de uso normales del agente ("ponme una cita el 22 de septiembre", "reúnete el lunes a las 10")
  devuelven `400` (fecha sin offset/`timeZone`, y `dateTime` con valor de sólo fecha). Además `end` se rellena con `start`
  (evento de duración cero) cuando el usuario no da hora de fin.
- **Fix propuesto:**

  ```python
  from datetime import datetime, timedelta, timezone

  def _event_dt(value: str, default_tz: str = "Europe/Madrid") -> dict:
      if len(value) == 10:                                   # "yyyy-mm-dd" -> todo el dia
          return {"date": value}
      dt = datetime.fromisoformat(value)
      if dt.tzinfo is None:                                  # sin offset -> hay que dar timeZone
          return {"dateTime": dt.isoformat(), "timeZone": default_tz}
      return {"dateTime": dt.isoformat()}

  def calendar_create(title, start, end="", attendees=None):
      start_obj = _event_dt(start)
      end_obj = _event_dt(end) if end else _default_end(start_obj)   # +1h o +1 dia, nunca duracion 0
      body = {"summary": title, "start": start_obj, "end": end_obj}
  ```

### A-5 · `drive_read` no puede leer Google Sheets/Slides/Docs no-Document

- **Dónde:** `tools/drive.py:13-31`. El `if "google-apps" in mime` mete todos los ficheros de Workspace, pero **sólo**
  `google-apps.document` usa `/export`; Sheets/Slides caen al `alt=media`.
- **Evidencia** (`drive_read("SHEET_ID")` con `mimeType=application/vnd.google-apps.spreadsheet`):

  ```
  llamadas=[('GET', '.../files/SHEET_ID', {'fields': 'id,name,mimeType,size'}),
            ('GET', '.../files/SHEET_ID', {'alt': 'media'})]     # <- no usa /export
  ```
- **Contrato oficial** (`files.get`): _"If you provide the URL parameter `alt=media`, then the response includes the file
  contents... **Downloading content with alt=media only works if the file is stored in Drive. To download Google Docs, Sheets,
  and Slides use `files.export` instead.**"_
- **Impacto:** la herramienta principal de Drive del agente falla con `403 fileNotDownloadable` en cualquier hoja de cálculo
  o presentación (los tipos más habituales), y el error llega al usuario como `{"error": "..."}` de la tool.
- **Fix propuesto:** exportar por tipo (`text/csv` para Sheets, `text/plain` para Slides/Docs) y usar `alt=media` sólo si el
  `mimeType` no empieza por `application/vnd.google-apps`:

  ```python
  EXPORT = {"application/vnd.google-apps.document": "text/plain",
            "application/vnd.google-apps.spreadsheet": "text/csv",
            "application/vnd.google-apps.presentation": "text/plain"}
  if mime in EXPORT:
      r = httpx.get(f"{BASE}/files/{file_id}/export", headers=headers(),
                    params={"mimeType": EXPORT[mime]}, timeout=30)
  ```

## 5. Hallazgos medios

### M-1 · `drive_search` construye la query sin escapar

- **Dónde:** `tools/drive.py:34` (`params={"q": f"name contains '{name}' and trashed=false"}`) y `tools/drive.py:8` (`folder_id`).
- **Evidencia:** `drive_search("O'Brien")` genera `q = "name contains 'O'Brien' and trashed=false"` ⇒ la sintaxis de Drive
  rompe (comilla de cierre prematura) y la API devuelve `400 invalid`. Un usuario puede además inyectar operadores
  (`name contains 'x' or trashed=true`) y alterar la consulta.
- **Fix propuesto:** escapar la comilla simple y el backslash (`name.replace("\\", "\\\\").replace("'", "\\'")`) o validar el
  nombre con una lista blanca antes de interpolarlo.

### M-2 · El LLM puede pisar hechos del usuario y los descartes silenciosos se reportan como éxito

- **Dónde:** `memory.py:63-73` (`semantic_set`), `agent.py:53-55` (`remember_fact` → siempre `{"ok": True}`).
- **Evidencia:**

  ```
  tras llm conf=1.0 -> 'ana@otra.com'   (el usuario había dicho ana@acme.com con conf 1.0)
  tras llm conf=0.5 -> valor sin cambios (no-op silencioso, y remember_fact habría devuelto ok=True)
  ```
- **Problemas:** (1) el corte por confianza no contempla el **origen** (un `remember_fact` del LLM con `confidence=1.0`,
  que es el valor por defecto del esquema, gana a lo que dijo el usuario); (2) cuando el early-return descarta la escritura,
  el handler devuelve `{"ok": True}` y el modelo cree que lo guardó: se pierde información sin traza ni aviso al usuario.
- **Fix propuesto:** priorizar `source` (`usuario` > `llm`), devolver `{"ok": False, "reason": "ignorado por menor confianza"}`
  en el descarte y registrar el conflicto en la memoria episódica.

### M-3 · `DATA_DIR` depende del directorio de trabajo

- **Dónde:** `config.py:17-18` (`DATA_DIR = Path("data")`).
- **Evidencia** (import del config desde otro `cwd`):

  ```
  DATA_DIR resuelto = C:\Users\Alfonso\AppData\Local\Temp\ma_audit\data   (cwd = carpeta temporal, no el repo)
  ```
- **Impacto:** `uvicorn api:app` o `streamlit run app.py` lanzados desde otra carpeta crean la memoria en otro sitio (memoria
  "desaparecida" y datos duplicados); en contenedores con `WORKDIR` distinto el efecto es el mismo.
- **Fix propuesto:** `DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent / "data"))`.

### M-4 · `episodic.jsonl` crece sin límite y cada evento reescribe todo el JSON

- **Dónde:** `memory.py:53-58` (recorta `memory.json` a 300 entradas y hace un `self._save()` completo) y `memory.py:47-50`
  (el `.jsonl` se abre en `"a"` sin ningún pruning).
- **Evidencia:**

  ```
  escritos=320 | memory.json episodic=300 | episodic.jsonl lineas=320
  ```
- **Impacto:** el `.jsonl` (que en teoría es el log append-only "real") crece indefinidamente; y cada evento hace una
  serialización + escritura completa del JSON (O(n) por evento, con n=300 → 300 escrituras completas por conversación de 300 turnos).
- **Fix propuesto:** rotación del `.jsonl` (p. ej. `episodic.1.jsonl` al superar N MB) y sacar el episódico del `memory.json`
  (guardar sólo el log en disco y mantener en RAM la ventana reciente).

### M-5 · `GOOGLE_API_KEY` del sistema puede enmascarar `GEMINI_API_KEY`

- **Dónde:** `agent.py:7` (`genai.Client(api_key=GEMINI_API_KEY)`), `config.py:7`.
- **Evidencia:**

  ```
  stderr al importar agent:  Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.
  google/genai/_api_client.py:140: logger.warning('Both GOOGLE_API_KEY and GEMINI_API_KEY are set. Using GOOGLE_API_KEY.')
  google/genai/_api_client.py:143: return env_google_api_key or env_gemini_api_key or None
  google/genai/client.py:719:      self.api_key = api_key or env_api_key
  entorno: GOOGLE_API_KEY presente (proceso y usuario) = True
  ```
- **Impacto:** hoy la clave pasada explícitamente gana, pero (1) el aviso se imprime en cada arranque y ensucia los logs,
  (2) si `GEMINI_API_KEY` falta o llega vacía (despliegue mal configurado, `.env` no cargado) el SDK usará **silenciosamente**
  la `GOOGLE_API_KEY` de la máquina, con la cuota/facturación de otro proyecto, y (3) `load_dotenv()` no sobrescribe variables
  ya presentes en el entorno, así que un `.env` con otra clave puede quedar ignorado en ese caso.
- **Fix propuesto:** validar y loguear al arranque qué clave se usará (mostrando sólo los últimos 4 caracteres) y usar
  `load_dotenv(override=True)` (o abortar el arranque si falta `GEMINI_API_KEY`) para que mande la configuración del repo.

### M-6 · El setup del README no funciona tal cual está escrito

- **Dónde:** `README.md:23` (`cp .env.example .env # rellena claves`), `README.md:44-47`.
- **Evidencia:** `.env.example=NO` (no existe en el repo ni en el historial: el único commit no lo incluye) y en el `.env`
  local **no hay** `DISCORD_BOT_TOKEN`, por lo que `discord_send`/`discord_read` responden siempre
  `{"error": "DISCORD_BOT_TOKEN no configurado"}`.
- **Fix propuesto:** añadir `.env.example` con todas las claves (`GEMINI_API_KEY`, `GEMINI_MODEL`, `GOOGLE_CLIENT_ID/SECRET/
  REFRESH_TOKEN`, `DISCORD_BOT_TOKEN`, `DISCORD_DEFAULT_CHANNEL_ID`, `DATA_DIR`, `ADMIN_API_KEY`) y un chequeo de arranque
  que enumere las que faltan.

### M-7 · No hay red de seguridad: sin tests, CI, lint config ni lockfile versionado

- **Evidencia:**

  ```
  .env.example=NO, tests=NO, pyproject.toml=NO, ruff.toml=NO, .github/workflows=NO,
  LICENSE=NO, Dockerfile=NO, frontend/package-lock.json=SI(untracked), Makefile=NO
  ```
- **Impacto:** nada de lo anterior salta antes de producción; `requirements.txt` sólo usa cotas inferiores (`>=`) y el
  lockfile de npm, creado al instalar, no está en git ⇒ dos despliegues no reproducen el mismo entorno.
- **Fix propuesto:** `tests/` con pytest para `memory.py`/`agent.py` con mocks (los 21 checks de esta auditoría sirven de base),
  workflow de CI (`pytest` + `ruff check` + `npm ci && npm run build`), un `ruff.toml` y versionar `package-lock.json`
  (usar `npm ci` en CI/deploy).
