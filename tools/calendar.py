from datetime import datetime, timezone
import httpx
from google_auth import headers
BASE = "https://www.googleapis.com/calendar/v3"

def calendar_list(max_results: int = 10) -> dict:
    r = httpx.get(f"{BASE}/calendars/primary/events", headers=headers(), params={
        "timeMin": datetime.now(timezone.utc).isoformat(), "maxResults": max_results, "singleEvents": "true", "orderBy": "startTime"}, timeout=30)
    r.raise_for_status()
    return {"events": [{"id": e["id"], "title": e.get("summary",""), "start": e.get("start",{}).get("dateTime",""), "end": e.get("end",{}).get("dateTime","")} for e in r.json().get("items", [])]}

def calendar_create(title: str, start: str, end: str = "", attendees: list = None) -> dict:
    body = {"summary": title, "start": {"dateTime": start}, "end": {"dateTime": end or start}}
    if attendees: body["attendees"]=[{"email": e} for e in attendees]
    r = httpx.post(f"{BASE}/calendars/primary/events", headers=headers(), json=body, timeout=30)
    r.raise_for_status()
    d=r.json()
    return {"id": d["id"], "link": d.get("htmlLink","")}
