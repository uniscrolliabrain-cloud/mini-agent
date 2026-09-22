"""Google Calendar API: listar y crear eventos."""
import datetime as dt

import httpx

from config import DEFAULT_TIMEZONE
from google_auth import headers

from ._util import clamp_int

BASE = "https://www.googleapis.com/calendar/v3"
TIMEOUT = 30


def _check(r: httpx.Response, action: str) -> None:
    if r.status_code >= 400:
        raise RuntimeError(f"{action} fallo ({r.status_code}): {r.text[:300]}")


def _event_time(value: str, default_tz: str = DEFAULT_TIMEZONE) -> dict:
    """Convierte lo que da el LLM en un EventDateTime valido para la API.

    - `2026-09-22` (todo el dia) -> {"date": ...}
    - `2026-09-22T10:00` (sin offset) -> {"dateTime": ..., "timeZone": tz}
      La API exige offset explicito o `timeZone`; antes se enviaba el valor tal
      cual y Google respondia 400.
    """
    raw = (value or "").strip()
    if not raw:
        raise ValueError("fecha vacia")
    if len(raw) == 10:
        try:
            dt.date.fromisoformat(raw)
        except ValueError as e:
            raise ValueError(f"fecha invalida {value!r}: {e}") from e
        return {"date": raw}
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"fecha-hora invalida {value!r} (usa ISO 8601): {e}") from e
    if parsed.tzinfo is None:
        return {"dateTime": parsed.isoformat(), "timeZone": default_tz}
    return {"dateTime": parsed.isoformat()}


def _default_end(start: dict) -> dict:
    """Fin por defecto: +1 hora, o +1 dia para eventos de todo el dia."""
    if "date" in start:
        end = dt.date.fromisoformat(start["date"]) + dt.timedelta(days=1)
        return {"date": end.isoformat()}
    end = dt.datetime.fromisoformat(start["dateTime"]) + dt.timedelta(hours=1)
    out = {"dateTime": end.isoformat()}
    if "timeZone" in start:
        out["timeZone"] = start["timeZone"]
    return out


def calendar_list(max_results: int = 10) -> dict:
    r = httpx.get(
        f"{BASE}/calendars/primary/events",
        headers=headers(),
        params={
            "timeMin": dt.datetime.now(dt.timezone.utc).isoformat(),
            "maxResults": clamp_int(max_results, 10, 1, 250),
            "singleEvents": "true",
            "orderBy": "startTime",
        },
        timeout=TIMEOUT,
    )
    _check(r, "calendar_list")
    events = []
    for e in r.json().get("items", []):
        start = e.get("start", {})
        end = e.get("end", {})
        events.append({
            "id": e.get("id", ""),
            "title": e.get("summary", ""),
            # los eventos de todo el dia vienen en `date`, no en `dateTime`
            "start": start.get("dateTime") or start.get("date", ""),
            "end": end.get("dateTime") or end.get("date", ""),
            "all_day": "date" in start,
        })
    return {"events": events}


def calendar_create(title: str, start: str, end: str = "", attendees: list | None = None) -> dict:
    start_obj = _event_time(start)
    end_obj = _event_time(end) if end else _default_end(start_obj)
    body = {"summary": title, "start": start_obj, "end": end_obj}
    if attendees:
        if isinstance(attendees, str):  # el LLM a veces manda una cadena
            attendees = [a.strip() for a in attendees.split(",") if a.strip()]
        body["attendees"] = [{"email": str(e)} for e in attendees]
    r = httpx.post(f"{BASE}/calendars/primary/events", headers=headers(), json=body, timeout=TIMEOUT)
    _check(r, "calendar_create")
    d = r.json()
    return {
        "id": d.get("id", ""),
        "link": d.get("htmlLink", ""),
        "start": start_obj,
        "end": end_obj,
        "invited": [a["email"] for a in body.get("attendees", [])],
    }

