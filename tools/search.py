"""Busqueda gratis DuckDuckGo + busqueda combinada email"""
from duckduckgo_search import DDGS
from .gmail import gmail_list

def web_search(query: str, max_results: int = 5) -> dict:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            out=[]
            for r in results:
                out.append({"title": r.get("title",""), "url": r.get("href",""), "snippet": r.get("body","")[:300]})
            return {"results": out, "query": query}
    except Exception as e:
        # fallback sin libreria - intenta con httpx a duckduckgo lite
        return {"results": [], "query": query, "error": str(e)}

def email_search(query: str) -> dict:
    """Busca en Gmail + web a la vez"""
    gmail_part = {"messages": []}
    try:
        gmail_part = gmail_list(max_results=5, query=query)
    except Exception as e:
        gmail_part = {"messages": [], "error": str(e)[:200]}
    web_part = web_search(query, max_results=5)
    return {"gmail": gmail_part, "web": web_part, "query": query}
