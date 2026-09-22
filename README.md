# mini-agent - vertical slice personal

**16 -> 22 ficheros, ~900 líneas. Sin kernel, sin multitenant, sin policy compleja.**

Ideas portadas del repo grande `uniscrolliabrain-cloud-agentic-os`:
- Memoria 4 capas con confidence + decay + goals (cognition/memory)
- INVARIANT_APPROVAL (policy/evaluator) -> bloquea gmail_send/discord_send en modo seguro
- SOPs versionados + GoalStack priorizado
- Episodic append-only jsonl + snapshot
- Tool risk classes

## Stack
- Backend: FastAPI + google-genai + DuckDuckGo gratis (duckduckgo-search)
- Frontend: React Vite tipo ChatGPT + Streamlit alternativo
- Memoria: data/<user_id>/memory.json + episodic.jsonl

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env # rellena claves
```

### Opcion A: Streamlit (rapido)
```bash
streamlit run app.py
# http://localhost:8501
```

### Opcion B: FastAPI + React (tipo ChatGPT)
```bash
# terminal 1
uvicorn api:app --reload --port 8000

# terminal 2
cd frontend
npm install
npm run dev
# http://localhost:5173
```

## .env
- GEMINI_API_KEY de aistudio.google.com (gratis)
- GOOGLE_CLIENT_ID/SECRET/REFRESH_TOKEN via OAuth Playground (scopes gmail, drive, calendar)
- DISCORD_BOT_TOKEN opcional

## Uso
- "me llamo Ana, mi email es ana@acme.com" -> guarda hecho con confidence
- "mi objetivo este mes es lanzar la agencia prioridad 90" -> goal
- "a partir de ahora cuando te pida briefing, busca emails + eventos + haz resumen" -> SOP
- "lee mis ultimos 5 emails" -> gmail_list
- "busca en la web como hacer OAuth refresh token" -> web_search gratis DuckDuckGo
- "busca a juan en email y web" -> email_search (combina gmail + web)
- Activa modo seguro para que no envie nada sin que quites el check.

## Deploy Streamlit Cloud
Sube a GitHub, conecta en share.streamlit.io, pon secrets en Settings.
Para React + API: deploy API en Render/Fly y frontend en Vercel con VITE_API_URL.
