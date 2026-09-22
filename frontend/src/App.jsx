import { useCallback, useEffect, useRef, useState } from "react";

// En desarrollo el proxy de vite manda /api -> http://localhost:8000.
// En produccion define VITE_API_URL con la URL publica de la API.
const API_BASE = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");
const API_KEY = import.meta.env.VITE_API_KEY || "";
const USER_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;

function authHeaders(extra = {}) {
  return API_KEY ? { ...extra, "X-API-Key": API_KEY } : extra;
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [userId, setUserId] = useState("default");
  const [safeMode, setSafeMode] = useState(true);
  const [memory, setMemory] = useState(null);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const chatRef = useRef(null);

  const fetchMemory = useCallback(async () => {
    if (!USER_ID_PATTERN.test(userId)) {
      setMemory(null);
      setError("user_id invalido: letras/numeros y . _ - (max 64, empezando por letra o numero).");
      return;
    }
    try {
      const r = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}`, { headers: authHeaders() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setMemory(await r.json());
      setError("");
    } catch (e) {
      setError(`No se pudo cargar la memoria: ${e.message}`);
    }
  }, [userId]);

  useEffect(() => {
    fetchMemory();
  }, [fetchMemory]);

  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight);
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setMessages((m) => [...m, { role: "user", content: text }]);
    try {
      const r = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ message: text, user_id: userId, safe_mode: safeMode })
      });
      const payload = await r.json().catch(() => null);
      if (!r.ok) {
        const detalle = payload?.detail;
        throw new Error(typeof detalle === "string" ? detalle : `HTTP ${r.status}`);
      }
      setMessages((m) => [...m, { role: "assistant", content: payload?.reply ?? "(respuesta vacia)" }]);
      if (payload?.snapshot) setMemory(payload.snapshot);
      setError("");
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", content: `Error: ${e.message}` }]);
    } finally {
      setSending(false);
    }
  };


  return (
    <div className="app">
      <div className="sidebar">
        <h3>🤖 Mini Agent</h3>
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="user_id"
          style={{ width: "100%", padding: "8px", borderRadius: "8px", background: "#1a1a27", border: "1px solid #242436", color: "#e5e5e5" }}
        />
        {error && <div className="alert">{error}</div>}
        <div style={{ marginTop: 12 }}>
          <label className="safe">
            <input type="checkbox" checked={safeMode} onChange={(e) => setSafeMode(e.target.checked)} /> Modo seguro (bloquea envios)
          </label>
        </div>
        <hr style={{ borderColor: "#242436", margin: "16px 0" }} />
        <div><strong>Hechos</strong> ({memory ? Object.keys(memory.semantic || {}).length : 0})</div>
        {memory?.semantic && Object.entries(memory.semantic).map(([k, v]) => (
          <div key={k} className="chip">{k}: {String(v).slice(0, 30)}</div>
        ))}
        <div style={{ marginTop: 12 }}><strong>Goals</strong> ({memory?.goals?.length || 0})</div>
        {memory?.goals?.slice(0, 5).map((g, i) => (
          <div key={i} className="chip">[{g.priority}] {String(g.description).slice(0, 40)}</div>
        ))}
        <div style={{ marginTop: 12 }}><strong>SOPs</strong> ({memory ? Object.keys(memory.procedural || {}).length : 0})</div>
        {memory?.procedural && Object.keys(memory.procedural).map((k) => <div key={k} className="chip">{k}</div>)}
        <div style={{ marginTop: 16 }}>
          <button
            onClick={fetchMemory}
            style={{ width: "100%", padding: "8px", borderRadius: "8px", background: "#1e1e2f", color: "#e5e5e5", border: "1px solid #242436" }}
          >
            Refrescar memoria
          </button>
        </div>
      </div>
      <div className="main">
        <div className="chat" ref={chatRef}>
          {messages.length === 0 && (
            <div style={{ color: "#9aa0b3", textAlign: "center", marginTop: "20%" }}>
              Gmail · Drive · Calendar · Discord · Web search gratis<br />
              Pregunta algo: "lee mis ultimos emails" o "busca en la web..."
            </div>
          )}
          {messages.map((m, i) => <div key={i} className={`bubble ${m.role}`}>{m.content}</div>)}
        </div>
        <div className="inputBar">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") send();
            }}
            placeholder="Escribe tu mensaje..."
          />
          <button onClick={send} disabled={sending}>{sending ? "Enviando..." : "Enviar"}</button>
        </div>
      </div>
    </div>
  );
}

