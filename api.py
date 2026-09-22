"""API HTTP del agente (FastAPI)."""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Path, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from agent import chat
from config import (
    ADMIN_API_KEY,
    CORS_ORIGINS,
    USER_ID_PATTERN,
    log_startup_status,
    missing_config,
)
from memory import InvalidUserId, MemoryStore, WorkingMemory

logger = logging.getLogger("mini_agent.api")

MAX_CACHED_USERS = 200  # tope de la cache en memoria (antes crecia sin limite)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(provided: str | None = Security(_api_key_header)) -> None:
    """Autenticacion por cabecera X-API-Key (fail closed)."""
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="ADMIN_API_KEY no configurada en el servidor")
    if provided != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="API key invalida")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log_startup_status()
    yield


app = FastAPI(title="Mini Agent API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # explicito, no "*"
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)

_stores: dict[str, MemoryStore] = {}
_workings: dict[str, WorkingMemory] = {}
_cache_order: list[str] = []
_lock = threading.Lock()


def get_store(user_id: str) -> tuple[MemoryStore, WorkingMemory]:
    """Devuelve (store, working) del usuario validando el id y con cache acotada."""
    try:
        with _lock:
            if user_id not in _stores:
                _stores[user_id] = MemoryStore(user_id)  # valida el identificador
                _workings[user_id] = WorkingMemory(cap=20)
                _cache_order.append(user_id)
                while len(_cache_order) > MAX_CACHED_USERS:
                    oldest = _cache_order.pop(0)
                    _stores.pop(oldest, None)
                    _workings.pop(oldest, None)
            else:
                _cache_order.remove(user_id)
                _cache_order.append(user_id)
            return _stores[user_id], _workings[user_id]
    except InvalidUserId as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    user_id: str = Field(default="default", pattern=USER_ID_PATTERN)
    safe_mode: bool = True


class ChatOut(BaseModel):
    reply: str
    snapshot: dict


UserPath = Path(pattern=USER_ID_PATTERN, max_length=64)


@app.get("/health")
def health() -> dict:
    """Sin auth: lo usan los healthchecks de la plataforma."""
    return {"status": "ok", "config_complete": not missing_config()}


@app.post("/chat", response_model=ChatOut, dependencies=[Depends(require_api_key)])
def chat_endpoint(inp: ChatIn) -> ChatOut:
    store, working = get_store(inp.user_id)
    working.add("user", inp.message)
    try:
        reply = chat(inp.message, working, store, safe_mode=inp.safe_mode)
    except Exception as e:
        logger.exception("chat fallo para %s", inp.user_id)
        raise HTTPException(status_code=500, detail=f"error interno: {e}") from e
    working.add("assistant", reply)
    return ChatOut(reply=reply, snapshot=store.snapshot())


@app.get("/memory/{user_id}", dependencies=[Depends(require_api_key)])
def memory(user_id: str = UserPath) -> dict:
    store, _ = get_store(user_id)
    return store.snapshot()


@app.delete("/memory/{user_id}", dependencies=[Depends(require_api_key)])
def clear_memory(user_id: str = UserPath) -> dict:
    store, working = get_store(user_id)
    store.clear()
    working.clear()
    return {"ok": True, "user_id": user_id}

