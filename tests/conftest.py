"""Pytest configuration for x0tta6bl4."""

import sys
import types

try:
    import oqs as _REAL_OQS_MODULE
except ImportError:
    _REAL_OQS_MODULE = None

# Heavy/missing deps that break collection or test startup.
_eth_account = types.ModuleType("eth_account")
_eth_account.messages = types.SimpleNamespace(encode_defunct=lambda **kwargs: kwargs.get("text", ""))
_eth_account.Account = type("Account", (), {
    "create": staticmethod(lambda **kwargs: types.SimpleNamespace(
        address="0x0000000000000000000000000000000000000001",
        key=types.SimpleNamespace(hex=lambda: "0x" + "0" * 64),
        sign_message=lambda message: types.SimpleNamespace(signature="0x" + "0" * 130, message_hash="0x" + "0" * 64)
    )),
    "from_key": staticmethod(lambda key: _eth_account.Account.create()),
})
sys.modules["eth_account"] = _eth_account
sys.modules["eth_account.messages"] = _eth_account.messages

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
    sys.modules.setdefault(_mod_name, _mod)

_eth = sys.modules.setdefault("eth_account")
_eth.messages = types.ModuleType("eth_account.messages")
sys.modules.setdefault("eth_account.messages", _eth.messages)
_eth.messages.encode_defunct = lambda **kwargs: kwargs.get("text", "")
_eth.Account = type("Account", (), {
    "create": staticmethod(lambda **kwargs: type("AccountInstance", (), {
        "address": "0x" + "0"*40,
        "key": type("Key", (), {"hex": lambda self: "0x" + "0"*64})(),
        "sign_message": lambda self, message: type("Signature", (), {"signature": "0x" + "0"*130, "messageHash": "0x" + "0"*64})()
    })()),
    "from_key": staticmethod(lambda key: _eth.Account.create()),
})
_eth.recover_message = lambda *args, **kwargs: "0x" + "0"*40

_prom = sys.modules["prometheus_client"]
_prom.CollectorRegistry = type("CollectorRegistry", (), {
    "__call__": lambda s, *a, **kw: types.SimpleNamespace(
        get_sample_value=lambda *a: 0.0, names=lambda self: iter([])
    ),
    "get_sample_value": lambda *a: 0.0,
    "names": lambda self: iter([]),
})
_prom.Counter = lambda *a, **kw: types.SimpleNamespace(
    inc=lambda *args, **kwargs: None, labels=lambda **kw: types.SimpleNamespace(inc=lambda *args, **kwargs: None)
)
_prom.Gauge = lambda *a, **kw: types.SimpleNamespace(
    set=lambda v: None, inc=lambda *args, **kwargs: None,
    labels=lambda **kw: types.SimpleNamespace(set=lambda v: None)
)
_prom.Histogram = lambda *a, **kw: types.SimpleNamespace(
    observe=lambda v: None, labels=lambda **kw: types.SimpleNamespace(observe=lambda v: None)
)
_prom.Summary = lambda *a, **kw: types.SimpleNamespace(observe=lambda v: None)
_prom.generate_latest = lambda *a, **kw: b""  # noqa: E731 — simple mock fallback
_prom.CONTENT_TYPE_LATEST = "text/plain"
_prom.REGISTRY = types.SimpleNamespace(_names_to_collectors={})
_prom.start_http_server = lambda *a, **kw: None

import asyncio
import os
import threading
import unittest.mock as mock
from contextlib import asynccontextmanager

import pytest
import httpx


class SandboxSafeTestClient:
    """Minimal synchronous TestClient shim for sandboxed CI."""

    def __init__(
        self,
        app,
        base_url="http://testserver",
        raise_server_exceptions=True,
        root_path="",
        backend="asyncio",
        backend_options=None,
        cookies=None,
        headers=None,
        follow_redirects=True,
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
            running = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

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
        async def _do_request():
            transport = httpx.ASGITransport(
                app=self.app,
                raise_app_exceptions=self.raise_server_exceptions,
                root_path=self.root_path,
                client=self.client,
            )
            async with httpx.AsyncClient(
                transport=transport,
                base_url=self.base_url,
                headers=self.headers,
                cookies=self.cookies,
                follow_redirects=kwargs.pop("follow_redirects", self.follow_redirects),
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


def _load_sys_path():
    return list(sys.path)


pytest.register_assert_rewrite("tests")
_pytest_sys_path = _load_sys_path()


@pytest.fixture(autouse=True)
def _preserve_sys_path(monkeypatch):
    baseline = _pytest_sys_path

    def _restore():
        current = [str(p) for p in sys.path]
        allowed = []
        for p in current:
            if any(str(b) == str(p) or p.endswith(os.sep + "site-packages") for b in baseline):
                allowed.append(p)
        keep = set(map(str, baseline))
        keep.update(allowed)
        new_path = [p for p in sys.path if str(p) in keep]
        while len(new_path) < len(baseline):
            new_path.append(os.pardir)
        sys.path[:] = new_path

    yield
    _restore()


@pytest.fixture(autouse=True)
def _prevent_hermes_test_site_packages(monkeypatch):
    """Block installer site-packages from leaking into pytest sys.path."""

    def _clean_path():
        bad_prefixes = (
            os.path.expanduser("~/.hermes/hermes-agent/venv"),
            os.path.expandvars(r"%USERPROFILE%\.hermes\hermes-agent\venv"),
        )
        cleaned = []
        removed = []
        for p in sys.path:
            if any(str(p).startswith(bad) for bad in bad_prefixes):
                removed.append(str(p))
                continue
            cleaned.append(p)
        sys.path[:] = cleaned
        if removed:
            import warnings
            warnings.warn(
                f"Removed hermetic site-packages from sys.path during tests: {removed}",
                RuntimeWarning,
                stacklevel=3,
            )

    _clean_path()
    yield
    _clean_path()


try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

_PREIMPORT_TIMEOUT = 5


def _is_module_available(name):
    if name in sys.modules:
        return False
    import importlib.util
    spec = importlib.util.find_spec(name)
    if spec is None:
        return False
    SLOW_MODULES = {
        "torch",
        "torch_geometric",
        "sentence_transformers",
        "flwr",
        "src.dao.governance_script",
        "prometheus_client",
    }
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

_batch_import_safe(
    "torch",
    "torch_geometric",
    "src.dao.governance_script",
    "prometheus_client",
    "sqlalchemy",
)

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
        with mock.patch(
            "src.dao.governance_script.Web3",
            mocked_modules["web3"].Web3,
            create=True,
        ):
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
    with mock.patch(
        "src.security.post_quantum_liboqs.LIBOQS_AVAILABLE",
        True,
    ), mock.patch(
        "src.security.post_quantum_liboqs.PQMeshSecurityLibOQS"
    ) as mock_pqc:
        yield mock_pqc


@pytest.fixture
def mock_ml():
    with mock.patch(
        "src.ml.graphsage_anomaly_detector.GraphSAGEAnomalyDetector"
    ) as mock_detector:
        yield mock_detector


def latency_threshold(seconds: float = 5.0) -> float:
    """Return latency threshold scaled by CI_LATENCY_FACTOR env var."""
    import os
    factor = float(os.getenv("CI_LATENCY_FACTOR", "1.0"))
    return seconds * factor
