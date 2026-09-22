import streamlit as st
from agent import chat
from memory import MemoryStore, WorkingMemory

st.set_page_config(page_title="Mini Agent", page_icon="🤖", layout="wide")

if "working" not in st.session_state:
    st.session_state.working = WorkingMemory(cap=20)
if "store" not in st.session_state:
    st.session_state.store = MemoryStore("default")
if "messages" not in st.session_state:
    st.session_state.messages = []
if "safe_mode" not in st.session_state:
    st.session_state.safe_mode = True

with st.sidebar:
    st.title("🧠 Memoria")
    user_id = st.text_input("Usuario", value=st.session_state.store.user_id)
    if user_id and user_id != st.session_state.store.user_id:
        st.session_state.store = MemoryStore(user_id)
        st.session_state.messages=[]
        st.session_state.working.clear()
        st.rerun()
    snap = st.session_state.store.snapshot()
    st.checkbox("Modo seguro (bloquea envios)", value=st.session_state.safe_mode, key="safe_mode")
    st.markdown(f"### Hechos ({len(snap['semantic'])})")
    for k,v in snap["semantic"].items():
        meta = snap["semantic_meta"].get(k,{})
        st.markdown(f"- **{k}**: {v} `conf {meta.get('confidence',1):.1f}`")
    st.markdown(f"### Objetivos ({len(snap['goals'])})")
    for g in snap["goals"][:5]:
        st.caption(f"[{g['priority']}] {g['description']}")
    st.markdown(f"### SOPs ({len(snap['procedural'])})")
    for k, steps in snap["procedural"].items():
        st.caption(f"{k}: {len(steps)} pasos")
    st.divider()
    c1,c2 = st.columns(2)
    with c1:
        if st.button("Limpiar chat", use_container_width=True):
            st.session_state.messages=[]
            st.session_state.working.clear()
            st.rerun()
    with c2:
        if st.button("Borrar memoria", use_container_width=True):
            st.session_state.store.clear()
            st.session_state.messages=[]
            st.session_state.working.clear()
            st.rerun()

st.title("🤖 Mini Agent")
st.caption("Gmail · Drive · Calendar · Discord · Web Search gratis · Memoria con confianza + goals")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Que quieres hacer?"):
    st.session_state.messages.append({"role":"user","content":prompt})
    st.session_state.working.add("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                reply = chat(prompt, st.session_state.working, st.session_state.store, safe_mode=st.session_state.safe_mode)
            except Exception as e:
                reply = f"❌ Error: `{e}`"
        st.markdown(reply)
    st.session_state.messages.append({"role":"assistant","content":reply})
    st.session_state.working.add("assistant", reply)
    st.rerun()
