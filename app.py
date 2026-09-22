import streamlit as st

from agent import chat
from config import missing_config
from memory import InvalidUserId, MemoryStore, WorkingMemory

st.set_page_config(page_title="Mini Agent", page_icon="🤖", layout="wide")

if "working" not in st.session_state:
    st.session_state.working = WorkingMemory(cap=20)
if "store" not in st.session_state:
    st.session_state.store = MemoryStore("default")
if "messages" not in st.session_state:
    st.session_state.messages = []
if "safe_mode" not in st.session_state:
    # se define ANTES de crear el widget: si se pasa `value=` con `key=` ya
    # presente en session_state, Streamlit avisa y el valor que manda no queda claro
    st.session_state.safe_mode = True


def _reset_chat():
    st.session_state.messages = []
    st.session_state.working.clear()


with st.sidebar:
    st.title("🧠 Memoria")
    missing = missing_config()
    if missing:
        st.warning("Faltan claves en .env: " + ", ".join(missing))

    user_id = st.text_input("Usuario", value=st.session_state.store.user_id)
    if user_id and user_id != st.session_state.store.user_id:
        try:
            st.session_state.store = MemoryStore(user_id)
        except InvalidUserId as e:
            st.error(f"Usuario no valido: {e} (usa letras, numeros, . _ -)")
        else:
            _reset_chat()
            st.rerun()

    snap = st.session_state.store.snapshot()
    st.checkbox("Modo seguro (bloquea envios)", key="safe_mode")
    st.caption("Activalo para que gmail_send/discord_send e invitaciones pidan confirmacion.")

    st.markdown(f"### Hechos ({len(snap['semantic'])})")
    for k, v in snap["semantic"].items():
        meta = snap["semantic_meta"].get(k, {})
        try:
            conf = float(meta.get("confidence", 1.0))
        except (TypeError, ValueError):
            conf = 0.0
        st.markdown(f"- **{k}**: {v} `conf {conf:.1f}`")

    st.markdown(f"### Objetivos ({len(snap['goals'])})")
    for g in snap["goals"][:5]:
        st.caption(f"[{g['priority']}] {g['description']}")

    st.markdown(f"### SOPs ({len(snap['procedural'])})")
    for k, steps in snap["procedural"].items():
        st.caption(f"{k}: {len(steps)} pasos")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Limpiar chat", use_container_width=True):
            _reset_chat()
            st.rerun()
    with c2:
        if st.button("Borrar memoria", use_container_width=True):
            st.session_state.store.clear()
            _reset_chat()
            st.rerun()

st.title("🤖 Mini Agent")
st.caption("Gmail · Drive · Calendar · Discord · Web Search gratis · Memoria con confianza + goals")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Que quieres hacer?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.working.add("user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                reply = chat(
                    prompt,
                    st.session_state.working,
                    st.session_state.store,
                    safe_mode=st.session_state.safe_mode,
                )
            except Exception as e:
                reply = f"❌ Error: `{e}`"
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.session_state.working.add("assistant", reply)
    st.rerun()

