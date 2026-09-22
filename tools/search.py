"""Busqueda web gratis (DuckDuckGo) + busqueda combinada email."""
import logging
from functools import lru_cache

from ._util import clamp_int
from .gmail import gmail_list

logger = logging.getLogger("mini_agent.search")

MAX_WEB_RESULTS = 20


@lru_cache(maxsize=1)
def _ddgs_class():
    """Carga perezosa del cliente de busqueda.

    El paquete original `duckduckgo_search` se renombro a `ddgs`; se importa
    dentro de la funcion para que el resto de la app (y los tests) funcione
    aunque la dependencia opcional de busqueda no este instalada.
    """
    try:
        from ddgs import DDGS  # paquete vigente
        return DDGS
    except ModuleNotFoundError:
        logger.debug("ddgs no disponible, probando duckduckgo_search")
    try:
        from duckduckgo_search import DDGS  # paquete obsoleto pero aun importable
        return DDGS
    except ModuleNotFoundError as e:
        raise RuntimeError("falta la dependencia de busqueda web: pip install ddgs") from e


def web_search(query: str, max_results: int = 5) -> dict:
    q = (query or "").strip()
    if not q:
        return {"results": [], "query": query, "error": "query vacia"}
    limit = clamp_int(max_results, 5, 1, MAX_WEB_RESULTS)
    try:
        ddgs_cls = _ddgs_class()
        with ddgs_cls() as ddgs:
            raw = list(ddgs.text(q, max_results=limit))
    except Exception as e:  # noqa: BLE001 - frontera con una libreria externa
        logger.warning("web_search fallo: %s", e)
        return {"results": [], "query": q, "error": f"{type(e).__name__}: {e}"}

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("href") or r.get("url", ""),
            "snippet": (r.get("body") or "")[:300],
        }
        for r in raw
    ]
    if not results:
        # Un buscador bloqueado devuelve lista vacia sin excepcion: hay que
        # reportarlo como error para no hacer creer al usuario que no hay nada.
        return {"results": [], "query": q, "error": "sin resultados (buscador bloqueado o sin coincidencias)"}
    return {"results": results, "query": q}


def email_search(query: str) -> dict:
    """Busca en Gmail + web a la vez."""
    q = (query or "").strip()
    if not q:
        return {"gmail": {"messages": []}, "web": {"results": []}, "query": q, "error": "query vacia"}
    try:
        gmail_part = gmail_list(max_results=5, query=q)
    except Exception as e:  # noqa: BLE001 - gmail puede fallar por credenciales/cuota
        gmail_part = {"messages": [], "error": str(e)[:200]}
    return {"gmail": gmail_part, "web": web_search(q, max_results=5), "query": q}

