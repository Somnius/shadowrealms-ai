"""Pure unit tests: make `services.*` importable from backend/ without the app stack."""

import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import types

import pytest

# The CI unit job installs only pytest + cryptography. Modules under test import `requests`
# at the top; every test replaces the HTTP calls anyway, so a stub is enough when it's missing.
try:  # pragma: no cover - depends on the environment
    import requests  # noqa: F401
except ImportError:  # pragma: no cover
    _req = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    def _no_http(*a, **k):
        raise RequestException("no HTTP in unit tests")

    _req.RequestException = RequestException
    _req.post = _no_http
    _req.get = _no_http
    sys.modules["requests"] = _req


@pytest.fixture
def app_settings(monkeypatch):
    """In-memory replacement for services.ai_runtime_settings (no database)."""
    store = {}
    mod = types.ModuleType("services.ai_runtime_settings")
    mod.get_app_setting = lambda key, default=None: store.get(key, default)

    def _set(key, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            store.pop(key, None)
        else:
            store[key] = value

    mod.set_app_setting = _set
    mod.delete_app_setting = lambda key: store.pop(key, None)
    monkeypatch.setitem(sys.modules, "services.ai_runtime_settings", mod)
    return store
