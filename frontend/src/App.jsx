import { useState, useEffect, useRef } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [userId, setUserId] = useState("default");
  const [safeMode, setSafeMode] = useState(true);
  const [memory, setMemory] = useState(null);
  const chatRef = useRef(null);

  const fetchMemory = async () => {
    try {
      const r = await fetch(`${API}/memory/${userId}`);
      const j = await r.json();
      setMemory(j);
    } catch {}
  };

  useEffect(() => { fetchMemory(); }, [userId]);

  useEffect(() => {
    chatRef.current?.scrollTo(0, chatRef.current.scrollHeight);
  }, [messages]);

  const send = async () => {
    if (!input.trim()) return;
    const msg = input;
    setInput("");
    setMessages(m => [...m, { role: "user", content: msg }]);
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, user_id: userId, safe_mode: safeMode })
      });
      const j = await r.json();
      setMessages(m => [...m, { role: "assistant", content: j.reply }]);
      setMemory(j.snapshot);
    } catch (e) {
      setMessages(m => [...m, { role: "assistant", content: "Error: " + e.message }]);
    }
  };

  return (
    <div className="app">
      <div className="sidebar">
        <h3>🤖 Mini Agent</h3>
        <input value={userId} onChange={e=>setUserId(e.target.value)} placeholder="user_id" style={{width:"100%", padding:"8px", borderRadius:"8px", background:"#1a1a27", border:"1px solid #242436", color:"#e5e5e5"}}/>
        <div style={{marginTop:12}}>
          <label className="safe"><input type="checkbox" checked={safeMode} onChange={e=>setSafeMode(e.target.checked)}/> Modo seguro (bloquea envios)</label>
        </div>
        <hr style={{borderColor:"#242436", margin:"16px 0"}}/>
        <div><strong>Hechos</strong> ({memory ? Object.keys(memory.semantic||{}).length : 0})</div>
        {memory?.semantic && Object.entries(memory.semantic).map(([k,v])=> <div key={k} className="chip">{k}: {String(v).slice(0,30)}</div>)}
        <div style={{marginTop:12}}><strong>Goals</strong> ({memory?.goals?.length||0})</div>
        {memory?.goals?.slice(0,5).map((g,i)=><div key={i} className="chip">[{g.priority}] {g.description.slice(0,40)}</div>)}
        <div style={{marginTop:12}}><strong>SOPs</strong> ({memory ? Object.keys(memory.procedural||{}).length : 0})</div>
        {memory?.procedural && Object.keys(memory.procedural).map(k=> <div key={k} className="chip">{k}</div>)}
        <div style={{marginTop:16}}>
          <button onClick={fetchMemory} style={{width:"100%", padding:"8px", borderRadius:"8px", background:"#1e1e2f", color:"#e5e5e5", border:"1px solid #242436"}}>Refrescar memoria</button>
        </div>
      </div>
      <div className="main">
        <div className="chat" ref={chatRef}>
          {messages.length===0 && <div style={{color:"#9aa0b3", textAlign:"center", marginTop:"20%"}}>Gmail · Drive · Calendar · Discord · Web search gratis<br/>Pregunta algo: "lee mis ultimos emails" o "busca en la web..."</div>}
          {messages.map((m,i)=><div key={i} className={`bubble ${m.role}`}>{m.content}</div>)}
        </div>
        <div className="inputBar">
          <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter" && send()} placeholder="Escribe tu mensaje..." />
          <button onClick={send}>Enviar</button>
        </div>
      </div>
    </div>
  );
}
