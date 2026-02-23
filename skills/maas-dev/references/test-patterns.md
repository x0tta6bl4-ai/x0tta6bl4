# MaaS Unit Test Patterns

## File Naming Convention

```
tests/unit/api/endpoints/test_{module}_unit.py
```
Examples: `test_batman_unit.py`, `test_nodes_unit.py`, `test_billing_unit.py`

## Standard Imports

```python
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import subprocess  # for endpoints that call batctl

import pytest
from fastapi import HTTPException

from src.api.maas.auth import UserContext
from src.api.maas.endpoints import mymod as mod
```

## Fixtures

```python
USER = UserContext(user_id="owner-1", plan="starter")
OTHER_USER = UserContext(user_id="other-1", plan="starter")
```

## Mocking the Mesh Registry

```python
def test_returns_404_when_mesh_not_found(monkeypatch):
    monkeypatch.setattr(mod, "get_mesh", lambda _id: None)
    with pytest.raises(HTTPException) as exc:
        await mod.my_endpoint("mesh-x", user=USER)
    assert exc.value.status_code == 404

def test_owner_skips_acl(monkeypatch):
    instance = SimpleNamespace(owner_id="owner-1", node_instances={"n1": object()})
    monkeypatch.setattr(mod, "get_mesh", lambda _id: instance)
    called = {"require": 0}
    async def _require(_m, _u): called["require"] += 1
    monkeypatch.setattr(mod, "require_mesh_access", _require)
    await mod.my_endpoint("mesh-1", user=USER)
    assert called["require"] == 0
```

## Mocking Async Services

```python
# For async service methods (run_health_checks, collect, run_cycle)
monitor = MagicMock()
monitor.run_health_checks = AsyncMock(return_value=mock_report)
monkeypatch.setattr(mod, "get_batman_health_monitor", lambda _n, _i: monitor)

# For sync methods (get_health_history, get_status)
monitor = MagicMock()
monitor.get_health_history.return_value = [r1, r2]
```

## CRITICAL: FastAPI Query() Objects

When calling endpoints directly in tests, always pass `interface` explicitly.
FastAPI `Query("bat0")` is NOT a string — it's a descriptor object.

```python
# WRONG — raises pydantic ValidationError because interface=Query("bat0")
resp = await mod.get_batman_originators("node-1", user=USER)

# CORRECT
resp = await mod.get_batman_originators("node-1", interface="bat0", user=USER)
```

## Testing subprocess Calls (batctl, kubectl, etc.)

```python
@pytest.mark.asyncio
async def test_raises_503_when_tool_not_found(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    with pytest.raises(HTTPException) as exc:
        await mod.get_originators("node-1", interface="bat0", user=USER)
    assert exc.value.status_code == 503

@pytest.mark.asyncio
async def test_raises_504_on_timeout(monkeypatch):
    def _raise(*a, **kw): raise subprocess.TimeoutExpired(["batctl"], 5)
    monkeypatch.setattr(subprocess, "run", _raise)
    with pytest.raises(HTTPException) as exc:
        await mod.get_originators("node-1", interface="bat0", user=USER)
    assert exc.value.status_code == 504
```

## Testing Import Failures (optional modules)

```python
@pytest.mark.asyncio
async def test_raises_503_when_module_unavailable(monkeypatch):
    import builtins
    original_import = builtins.__import__
    def _bad_import(name, *args, **kwargs):
        if "myoptional" in name:
            raise ImportError("no module")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", _bad_import)
    with pytest.raises(HTTPException) as exc:
        await mod.my_endpoint("node-1", user=USER)
    assert exc.value.status_code == 503
```

## Testing Global Instance Caches

Always clear caches in setup_method:

```python
class TestMyMonitor:
    def setup_method(self):
        mod._my_monitors.clear()

    def test_cached(self, monkeypatch):
        FakeClass = MagicMock(return_value=MagicMock())
        monkeypatch.setattr(mylib, "MyMonitor", FakeClass)
        m1 = mod.get_my_monitor("n1", "bat0")
        m2 = mod.get_my_monitor("n1", "bat0")
        assert m1 is m2
        assert FakeClass.call_count == 1
```

## Pydantic Model Tests

```python
def test_default_values():
    req = mod.MyRequest(action="restart")
    assert req.force is False
    assert req.target is None

def test_required_field_missing():
    with pytest.raises(Exception):  # pydantic ValidationError
        mod.MyRequest()
```

## AsyncMock vs MagicMock

```python
# AsyncMock: for functions defined with async def
collector.collect = AsyncMock(return_value=snapshot)

# MagicMock: for sync functions (even if returned from AsyncMock)
collector.get_metrics_output = MagicMock(return_value="# metrics\n")

# TRAP: AsyncMock auto-makes child attrs as AsyncMock too
# So if collector = AsyncMock(), then collector.get_metrics_output is also AsyncMock
# and calling it returns a coroutine, not a string.
# Fix: use MagicMock() for the parent when you need sync child methods:
collector = MagicMock()
collector.collect = AsyncMock(return_value=snapshot)
collector.get_metrics_output = MagicMock(return_value="...")
```
