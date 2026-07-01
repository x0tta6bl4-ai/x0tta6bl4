"""Pytest configuration for x0tta6bl4.

Ensures that the project root is on sys.path so imports like `from src...` work
in unit tests regardless of the working directory.
"""

# ---------------------------------------------------------------------------
# CRITICAL: Mock heavy dependencies BEFORE any other imports.
# Modules like prometheus_client, oqs, kubernetes cause import chain errors
# when not installed or version-mismatched. These mocks prevent that.
# ---------------------------------------------------------------------------
import sys
import types

_HEAVY_MOCKS = {
    "prometheus_client": types.ModuleType("prometheus_client"),
    "kubernetes": types.ModuleType("kubernetes"),
    "flwr": types.ModuleType("flwr"),
    "eth_account": types.ModuleType("eth_account"),
    "sentence_transformers": types.ModuleType("sentence_transformers"),
    "oqs": types.ModuleType("oqs"),
    "liboqs": types.ModuleType("liboqs"),
}
for _mod_name, _mod in _HEAVY_MOCKS.items():
    sys.modules[_mod_name] = _mod

# Give prometheus_client the expected names so imports don't crash
_prom = sys.modules["prometheus_client"]
_prom.CollectorRegistry = type("CollectorRegistry", (), {
    "__call__": lambda s, *a, **kw: types.SimpleNamespace(
        get_sample_value=lambda *a: 0.0, names=lambda self: iter([])
    ),
    "get_sample_value": lambda *a: 0.0,
    "names": lambda self: iter([]),
})
_prom.Counter = lambda *a, **kw: types.SimpleNamespace(
    inc=lambda: None, labels=lambda **kw: types.SimpleNamespace(inc=lambda: None)
)
_prom.Gauge = lambda *a, **kw: types.SimpleNamespace(
    set=lambda v: None, inc=lambda: None,
    labels=lambda **kw: types.SimpleNamespace(set=lambda v: None)
)
_prom.Histogram = lambda *a, **kw: types.SimpleNamespace(
    observe=lambda v: None,
    labels=lambda **kw: types.SimpleNamespace(observe=lambda v: None)
)
_prom.Summary = lambda *a, **kw: types.SimpleNamespace(observe=lambda v: None)
_prom.generate_latest = lambda: b""
_prom.CONTENT_TYPE_LATEST = "text/plain"
_prom.REGISTRY = types.SimpleNamespace(
    _names_to_collectors={},
)
_prom.start_http_server = lambda *a, **kw: None

# Now safe to import everything else
import asyncio
import os
import threading
import unittest.mock as mock
from contextlib import asynccontextmanager

import pytest
import httpx


class SandboxSafeTestClient:
    """Minimal TestClient compatible with sandbox constraints.

    Starlette/FastAPI TestClient uses anyio's blocking portal, which can hang
    in restricted environments. This client performs synchronous request calls
    via httpx.AsyncClient + ASGITransport without using blocking portals.
    """

    def __init__(
        self, app, base_url="http://testserver",
        raise_server_exceptions=True, root_path="",
        backend="asyncio", backend_options=None,
        cookies=None, headers=None, follow_redirects=True,
        client=("testclient", 50000),
    ):
        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path
        self.follow_redirects = follow_redirects
        self.client = client
        self.headers = dict(headers or {})
        self.headers.setdefault("user-agent", "testclient")
        self.cookies = httpx.Cookies(cookies)

    @staticmethod
    def _run_coro(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            try:
                return asyncio.run(coro)
            finally:
                try:
                    asyncio.get_event_loop()
                except RuntimeError:
                    asyncio.set_event_loop(asyncio.new_event_loop())
        result = {}
        error = {}
        def _runner():
            try:
                result["value"] = asyncio.run(coro)
            except Exception as exc:
                error["exc"] = exc
        thread = threading.Thread(target=_runner, daemon=True)
        thread.start()
        thread.join()
        if "exc" in error:
            raise error["exc"]
        return result.get("value")

    def request(self, method, url, **kwargs):
        follow_redirects = kwargs.pop("follow_redirects", self.follow_redirects)
        async def _do_request():
            transport = httpx.ASGITransport(
                app=self.app, raise_app_exceptions=self.raise_server_exceptions,
                root_path=self.root_path, client=self.client,
            )
            async with httpx.AsyncClient(
                transport=transport, base_url=self.base_url,
                headers=self.headers, cookies=self.cookies,
                follow_redirects=follow_redirects,
            ) as async_client:
                response = await async_client.request(method, url, **kwargs)
                self.cookies.update(response.cookies)
                return response
        return self._run_coro(_do_request())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)
    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)
    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)
    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)
    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)
    def options(self, url, **kwargs):
        return self.request("OPTIONS", url, **kwargs)
    def head(self, url, **kwargs):
        return self.request("HEAD", url, **kwargs)
    def close(self):
        return None
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

# Patch TestClient globally
try:
    import fastapi.testclient as fastapi_testclient
    import starlette.testclient as starlette_testclient
    fastapi_testclient.TestClient = SandboxSafeTestClient
    starlette_testclient.TestClient = SandboxSafeTestClient
except Exception:
    pass

@asynccontextmanager
async def _contextmanager_inline(cm):
    value = cm.__enter__()
    try:
        yield value
    except Exception as exc:
        suppress = cm.__exit__(type(exc), exc, exc.__traceback__)
        if not suppress:
            raise
    else:
        cm.__exit__(None, None, None)

try:
    import fastapi.concurrency as fastapi_concurrency
    import fastapi.dependencies.utils as fastapi_dependencies_utils
    import fastapi.routing as fastapi_routing
    import starlette.concurrency as starlette_concurrency
    fastapi_concurrency.contextmanager_in_threadpool = _contextmanager_inline
    fastapi_dependencies_utils.contextmanager_in_threadpool = _contextmanager_inline
    async def _run_in_threadpool_inline(func, *args, **kwargs):
        return func(*args, **kwargs)
    fastapi_concurrency.run_in_threadpool = _run_in_threadpool_inline
    fastapi_dependencies_utils.run_in_threadpool = _run_in_threadpool_inline
    fastapi_routing.run_in_threadpool = _run_in_threadpool_inline
    starlette_concurrency.run_in_threadpool = _run_in_threadpool_inline
except Exception:
    pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    root_index = sys.path.index(PROJECT_ROOT) if PROJECT_ROOT in sys.path else -1
    sys.path.insert(root_index + 1, SRC_ROOT)

if not hasattr(asyncio, "coroutine"):
    asyncio.coroutine = types.coroutine

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

_PREIMPORT_TIMEOUT = 5

def _is_module_available(name):
    # Already in sys.modules (possibly mocked) — skip
    if name in sys.modules:
        return False
    import importlib.util
    spec = importlib.util.find_spec(name)
    if spec is None:
        return False
    SLOW_MODULES = {"torch", "torch_geometric", "sentence_transformers", "flwr", "src.dao.governance_script", "prometheus_client"}
    if name in SLOW_MODULES:
        return False
    return True

def _import_safe(name):
    import importlib
    result = [None]
    exc_info = [None]
    def _load():
        try:
            result[0] = importlib.import_module(name)
        except BaseException as e:
            exc_info[0] = e
    t = threading.Thread(target=_load, daemon=True)
    t.start()
    t.join(timeout=_PREIMPORT_TIMEOUT)
    if t.is_alive():
        return
    if exc_info[0] is not None and not isinstance(exc_info[0], ImportError):
        return

def _batch_import_safe(*names):
    installed = [n for n in names if _is_module_available(n)]
    if not installed:
        return
    threads = []
    for name in installed:
        t = threading.Thread(target=_import_safe, args=(name,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=_PREIMPORT_TIMEOUT + 1)

_batch_import_safe("torch", "torch_geometric", "src.dao.governance_script", "prometheus_client", "sqlalchemy")

try:
    import sqlalchemy.orm
    import sqlalchemy.orm.base
    import sqlalchemy.ext.declarative
except Exception:
    pass

try:
    import cryptography
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except Exception:
    pass

try:
    import oqs as _REAL_OQS_MODULE
except ImportError:
    _REAL_OQS_MODULE = None

mocked_modules = {
    "liboqs": mock.MagicMock(),
    "oqs": mock.MagicMock(),
    "bcc": mock.MagicMock(),
    "prometheus_api_client": mock.MagicMock(),
    "sentence_transformers": mock.MagicMock(),
    "sentence_transformers.SentenceTransformer": mock.MagicMock(),
    "shap": mock.MagicMock(),
    "numba": mock.MagicMock(),
    "flwr": mock.MagicMock(),
    "web3": mock.MagicMock(),
    "aioipfs": mock.MagicMock(),
}

@pytest.fixture(autouse=True)
def mock_dependencies():
    with mock.patch.dict("sys.modules", mocked_modules):
        with mock.patch("src.dao.governance_script.Web3", mocked_modules["web3"].Web3, create=True):
            yield

@pytest.fixture
def real_oqs(monkeypatch):
    if _REAL_OQS_MODULE is None:
        pytest.skip("oqs not installed")
    monkeypatch.setitem(sys.modules, "oqs", _REAL_OQS_MODULE)
    yield _REAL_OQS_MODULE

@pytest.fixture
def production_mode(monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")

@pytest.fixture
def staging_mode(monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "false")

@pytest.fixture
def mock_pqc():
    with mock.patch("src.security.post_quantum_liboqs.LIBOQS_AVAILABLE", True):
        with mock.patch("src.security.post_quantum_liboqs.PQMeshSecurityLibOQS") as mock_pqc:
            yield mock_pqc

@pytest.fixture
def mock_ml():
    with mock.patch("src.ml.graphsage_anomaly_detector.GraphSAGEAnomalyDetector") as mock_detector:
        yield mock_detector


def latency_threshold(seconds: float = 5.0) -> float:
    """Return latency threshold scaled by CI_LATENCY_FACTOR env var."""
    import os
    factor = float(os.getenv("CI_LATENCY_FACTOR", "1.0"))
    return seconds * factor
