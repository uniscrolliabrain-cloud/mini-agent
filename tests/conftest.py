"""Configuracion de pytest: DATA_DIR temporal y mocks reutilizables.

IMPORTANTE: este fichero define el entorno ANTES de que los tests importen los
modulos del repo (config.py lee DATA_DIR y las claves en tiempo de import).
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Los tests NUNCA deben tocar datos ni credenciales reales del usuario:
# se aisla la memoria en un directorio temporal y se anulan las claves.
TMP_DATA = Path(tempfile.mkdtemp(prefix="mini-agent-tests-"))
os.environ["DATA_DIR"] = str(TMP_DATA)
os.environ["ADMIN_API_KEY"] = "test-api-key"
os.environ["GEMINI_API_KEY"] = ""  # evita crear un cliente real de Gemini
os.environ["DISCORD_BOT_TOKEN"] = ""
os.environ["DISCORD_DEFAULT_CHANNEL_ID"] = ""
os.environ.pop("GOOGLE_API_KEY", None)


class FakeResponse:
    """Respuesta minima compatible con lo que usan las tools."""

    def __init__(self, payload=None, text="", status_code=200, headers=None):
        self._payload = payload
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("respuesta sin JSON")
        return self._payload


class FakeHTTP:
    """Sustituye al modulo `httpx` dentro de una tool y registra las llamadas.

    Las reglas se evaluan en orden: (metodo, fragmento_de_url) -> respuesta. La
    respuesta puede ser un objeto o un callable que recibe los kwargs de la
    llamada (util cuando hay que distinguir por `params`).
    """

    def __init__(self, *rules, default=None):
        self.calls = []
        self.rules = list(rules)
        self.default = default

    def add(self, response, method=None, fragment=None):
        self.rules.append((method, fragment, response))
        return self

    def _dispatch(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        for rule_method, fragment, response in self.rules:
            if (rule_method is None or rule_method == method) and (fragment is None or fragment in url):
                return response(url=url, **kwargs) if callable(response) else response
        return self.default if self.default is not None else FakeResponse()

    def get(self, url, **kwargs):
        return self._dispatch("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._dispatch("POST", url, **kwargs)

    def urls(self):
        return [c["url"] for c in self.calls]


@pytest.fixture
def install_fake_http(monkeypatch):
    """Fixture: instala un FakeHTTP en el modulo indicado (y mockea `headers`)."""

    def _install(module, *rules, patch_headers=True, default=None):
        fake = FakeHTTP(*rules, default=default)
        if patch_headers and hasattr(module, "headers"):
            monkeypatch.setattr(module, "headers", lambda: {"Authorization": "Bearer test-token"})
        monkeypatch.setattr(module, "httpx", fake)
        return fake

    return _install


@pytest.fixture(autouse=True)
def _limpiar_memoria_temporal():
    """Deja limpio el DATA_DIR temporal y las caches de la API tras cada test."""
    import shutil

    yield

    api_mod = sys.modules.get("api")
    if api_mod is not None:  # evita que una cache apunte a datos ya borrados
        api_mod._stores.clear()
        api_mod._workings.clear()
        api_mod._cache_order.clear()
    for child in TMP_DATA.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
