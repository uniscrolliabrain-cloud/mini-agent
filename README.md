# mini-agent - vertical slice personal

Asistente personal con memoria en 4 capas que opera **Gmail, Drive, Calendar, Discord y busqueda web**.

- **Backend:** FastAPI + `google-genai` (Gemini) + `ddgs` (busqueda web gratis)
- **Frontend:** React + Vite (tipo ChatGPT) y alternativa en Streamlit
- **Memoria:** `data/<user_id>/memory.json` (con backup y escritura atomica) + `episodic.jsonl` (append-only con rotacion)
- **Politica:** invariante de aprobacion por *efecto* de cada tool (`safe_mode`)

Ideas portadas del repo grande `uniscrolliabrain-cloud-agentic-os`: memoria con `confidence` + decay + goals,
INVARIANT_APPROVAL, SOPs versionados, episodic append-only y clases de riesgo por tool.

## Requisitos

- Python **3.10+** (probado con 3.12)
- Node 18+ para el frontend React

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # desarrollo: pip install -r requirements-dev.txt

cp .env.example .env               # rellena las claves (ver abajo)
```

### Opcion A: Streamlit (rapido)

```bash
streamlit run app.py
# http://localhost:8501
```

### Opcion B: FastAPI + React

```bash
# terminal 1
uvicorn api:app --reload --port 8000

# terminal 2
cd frontend
npm install                        # CI/deploy: npm ci
cp .env.example .env               # VITE_API_URL (opcional) y VITE_API_KEY
npm run dev
# http://localhost:5173
```

En desarrollo, Vite hace proxy de `/api/*` a `http://localhost:8000`, asi que no hace falta configurar CORS ni
`VITE_API_URL`. En produccion define `VITE_API_URL` con la URL publica de la API.

## Variables de entorno

| Clave | Obligatoria | Descripcion |
|---|---|---|
| `GEMINI_API_KEY` | Si | Clave de [aistudio.google.com](https://aistudio.google.com/apikey). Gratis. |
| `GEMINI_MODEL` | No | Default `gemini-2.5-flash`. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` | Si (Gmail/Drive/Calendar) | OAuth con scopes `gmail.readonly`, `gmail.send`, `gmail.compose`, `drive.readonly`, `calendar.readonly`, `calendar.events`. |
| `DISCORD_BOT_TOKEN` / `DISCORD_DEFAULT_CHANNEL_ID` | No | Sin token, las tools de Discord responden error explicito. |
| `ADMIN_API_KEY` | Si (API HTTP) | Protege `/chat` y `/memory/*` con la cabecera `X-API-Key`. Si falta, la API responde **503** (fail closed). |
| `CORS_ORIGINS` | No | Lista separada por comas. Default `http://localhost:5173,http://localhost:8501`. |
| `DEFAULT_TIMEZONE` | No | Zona IANA para eventos sin offset. Default `Europe/Madrid`. |
| `DATA_DIR` | No | Carpeta de memoria. Default `./data` (junto al codigo, no depende del `cwd`). |

> **Importante:** `GEMINI_API_KEY` tiene prioridad sobre cualquier `GOOGLE_API_KEY` que exista en el sistema; al
> arrancar se logea que clave se usa (solo los ultimos 4 caracteres).

## Uso

- "me llamo Ana, mi email es ana@acme.com" → guarda el hecho con `confidence` y fuente
- "mi objetivo este mes es lanzar la agencia, prioridad 90" → goal
- "a partir de ahora cuando te pida briefing, busca emails + eventos + haz resumen" → SOP versionado
- "lee mis ultimos 5 emails" → `gmail_list`
- "busca en la web como hacer OAuth refresh token" → `web_search` (gratis, sin API key)
- "busca a juan en email y web" → `email_search` (Gmail + web)
- "ponme una cita el 22 de septiembre" → evento de todo el dia; "reunion manana a las 10" → con `timeZone`
- **Modo seguro** (activado por defecto): bloquea `gmail_send`, `discord_send` y las invitaciones de `calendar_create`
  hasta que lo desactives o confirmes.

## API

| Metodo | Ruta | Auth | Descripcion |
|---|---|---|---|
| GET | `/health` | No | Healthcheck (no expone datos). |
| POST | `/chat` | `X-API-Key` | `{message, user_id, safe_mode}` → `{reply, snapshot}` |
| GET | `/memory/{user_id}` | `X-API-Key` | Snapshot de memoria. |
| DELETE | `/memory/{user_id}` | `X-API-Key` | Borra la memoria del usuario. |

`user_id` se valida con `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` (se rechaza `..`, `/`, `\`, etc.) y `safe_mode` es `true`
por defecto.

## Tests y lint

```bash
pip install -r requirements-dev.txt
ruff check .          # lint Python (config en ruff.toml)
pytest -q             # 100 tests, sin red
cd frontend && npm run lint && npm run build
```

## Deploy

- **Streamlit Cloud:** sube el repo, conecta en share.streamlit.io y define los secrets en *Settings*.
- **API (Docker/Render/Fly/...):**
  ```bash
  docker build -t mini-agent-api .
  docker run -p 8000:8000 --env-file .env -v mini-agent-data:/data mini-agent-api
  ```
  El `Dockerfile` usa `DATA_DIR=/data` (monta un volumen para persistir la memoria) y expone `/health` como healthcheck.
- **Frontend (Vercel/Netlify):** build `npm ci && npm run build`, define `VITE_API_URL` (URL de la API) y `VITE_API_KEY`
  (= `ADMIN_API_KEY`).

> La `ADMIN_API_KEY` viaja en el bundle del frontend, asi que no es un secreto fuerte: es una barrera contra
> peticiones anonimas. Para exposicion publica real, pon la API detras de un proxy con login.

## Estructura

```
agent.py          orquestador: bucle de tools + invariante de aprobacion (run_tool)
api.py            FastAPI: auth X-API-Key, validacion de user_id, /health
app.py            UI Streamlit
config.py         configuracion, patron de user_id y politica de aprobacion (TOOL_EFFECTS)
memory.py         memoria 4 capas, escritura atomica + backup, log episodico con rotacion
google_auth.py    refresh de access token de Google (cache en disco + lock)
tools/            gmail, drive, calendar, discord, search (+ _util compartido)
frontend/         React + Vite
tests/            pytest (mocks de httpx y de Gemini, sin llamadas reales)
AUDIT.md          auditoria de seguridad/calidad y estado de las correcciones
```

