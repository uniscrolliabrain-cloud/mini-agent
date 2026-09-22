from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from memory import MemoryStore, WorkingMemory
from agent import chat

app = FastAPI(title="Mini Agent API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

stores: dict[str, MemoryStore] = {}
workings: dict[str, WorkingMemory] = {}

def get_store(user_id: str):
    if user_id not in stores:
        stores[user_id]=MemoryStore(user_id)
        workings[user_id]=WorkingMemory(cap=20)
    return stores[user_id], workings[user_id]

class ChatIn(BaseModel):
    message: str
    user_id: str = "default"
    safe_mode: bool = True

class ChatOut(BaseModel):
    reply: str
    snapshot: dict

@app.post("/chat", response_model=ChatOut)
def chat_endpoint(inp: ChatIn):
    store, working = get_store(inp.user_id)
    working.add("user", inp.message)
    reply = chat(inp.message, working, store, safe_mode=inp.safe_mode)
    working.add("assistant", reply)
    return ChatOut(reply=reply, snapshot=store.snapshot())

@app.get("/memory/{user_id}")
def memory(user_id: str):
    store,_ = get_store(user_id)
    return store.snapshot()

@app.delete("/memory/{user_id}")
def clear_memory(user_id: str):
    store, working = get_store(user_id)
    store.clear()
    working.clear()
    return {"ok": True}
