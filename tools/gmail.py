import base64
from email.mime.text import MIMEText
import httpx
from google_auth import headers

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

def gmail_list(max_results: int = 10, query: str = "") -> dict:
    params = {"maxResults": max_results}
    if query: params["q"] = query
    r = httpx.get(f"{BASE}/messages", headers=headers(), params=params, timeout=30)
    r.raise_for_status()
    out=[]
    for m in r.json().get("messages", []):
        d = httpx.get(f"{BASE}/messages/{m['id']}", headers=headers(), params={"format": "metadata", "metadataHeaders": ["From","Subject"]}, timeout=30).json()
        h = {x["name"]: x["value"] for x in d.get("payload", {}).get("headers", [])}
        out.append({"id": m["id"], "from": h.get("From",""), "subject": h.get("Subject",""), "snippet": d.get("snippet","")})
    return {"messages": out}

def gmail_send(to: str, subject: str, body: str) -> dict:
    msg = MIMEText(body)
    msg["to"]=to
    msg["subject"]=subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = httpx.post(f"{BASE}/messages/send", headers=headers(), json={"raw": raw}, timeout=30)
    r.raise_for_status()
    return {"id": r.json().get("id",""), "status": "sent", "to": to}

def gmail_create_draft(to: str, subject: str, body: str) -> dict:
    msg = MIMEText(body)
    msg["to"]=to
    msg["subject"]=subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = httpx.post(f"{BASE}/drafts", headers=headers(), json={"message": {"raw": raw}}, timeout=30)
    r.raise_for_status()
    return {"id": r.json().get("id",""), "status": "draft"}
