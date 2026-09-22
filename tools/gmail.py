"""Gmail API: listar, enviar y crear borradores."""
import base64
from email.mime.text import MIMEText
from email.utils import formatdate

import httpx

from google_auth import headers

from ._util import clamp_int

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
TIMEOUT = 30


def _check(r: httpx.Response, action: str) -> None:
    """raise_for_status que incluye el motivo que devuelve Google."""
    if r.status_code >= 400:
        raise RuntimeError(f"{action} fallo ({r.status_code}): {r.text[:300]}")


def _raw_message(to: str, subject: str, body: str) -> str:
    """Construye el mensaje RFC 5322 y lo devuelve en base64url."""
    # charset explicito: el default us-ascii obliga a Python a adivinar el charset
    # con texto acentuado (lo hace bien, pero no queremos depender de ese fallback).
    msg = MIMEText(body, "plain", "utf-8")
    msg["to"] = to
    msg["subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def gmail_list(max_results: int = 10, query: str = "") -> dict:
    params = {"maxResults": clamp_int(max_results, 10, 1, 100)}
    if query:
        params["q"] = query
    r = httpx.get(f"{BASE}/messages", headers=headers(), params=params, timeout=TIMEOUT)
    _check(r, "gmail_list")
    out = []
    for m in r.json().get("messages", []):
        d = httpx.get(
            f"{BASE}/messages/{m['id']}",
            headers=headers(),
            params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
            timeout=TIMEOUT,
        ).json()
        h = {x["name"]: x["value"] for x in d.get("payload", {}).get("headers", [])}
        out.append({
            "id": m["id"],
            "from": h.get("From", ""),
            "subject": h.get("Subject", ""),
            "date": h.get("Date", ""),
            "snippet": d.get("snippet", ""),
        })
    return {"messages": out}


def gmail_send(to: str, subject: str, body: str) -> dict:
    r = httpx.post(
        f"{BASE}/messages/send",
        headers=headers(),
        json={"raw": _raw_message(to, subject, body)},
        timeout=TIMEOUT,
    )
    _check(r, "gmail_send")
    return {"id": r.json().get("id", ""), "status": "sent", "to": to}


def gmail_create_draft(to: str, subject: str, body: str) -> dict:
    r = httpx.post(
        f"{BASE}/drafts",
        headers=headers(),
        json={"message": {"raw": _raw_message(to, subject, body)}},
        timeout=TIMEOUT,
    )
    _check(r, "gmail_create_draft")
    return {"id": r.json().get("id", ""), "status": "draft", "to": to}

