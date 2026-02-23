---
name: maas-dev
description: "Develops MaaS (Mesh-as-a-Service) API endpoints, services, and unit tests for x0tta6bl4. Handles the full flow: implement endpoint, write tests, register ownership, commit with correct SWARM_AGENT. Use when user asks to: continue MaaS development, add MaaS endpoint, implement billing endpoint, batman endpoint, nodes endpoint, write MaaS tests, fix MaaS API, продолжай разработку maas, добавь endpoint, разработай MaaS сервис, протестируй MaaS."
---

# MaaS Dev

MaaS (Mesh-as-a-Service) development workflow for x0tta6bl4. All endpoints live in
`src/api/maas/endpoints/`, services in `src/api/maas/services.py`, tests in
`tests/unit/api/endpoints/test_{module}_unit.py`.

## Step 1: Identify the Target

Read `docs/STATUS.md` and `plans/NEXT_PRIORITIES_MESH_FL.md` to pick the next task.
Check existing endpoints:

```bash
ls src/api/maas/endpoints/
```

Key modules: `batman.py`, `nodes.py`, `billing.py`, `combined.py`, `mesh.py`.

## Step 2: Implement Endpoint

Follow the pattern from `src/api/maas/endpoints/batman.py`:

```python
from ..auth import UserContext, get_current_user, require_mesh_access
from ..registry import get_mesh
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/my-module", tags=["my-module"])

@router.get("/{node_id}/action")
async def my_action(
    node_id: str,
    user: UserContext = Depends(get_current_user),
) -> dict:
    instance = get_mesh(node_id)
    if instance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if instance.owner_id != user.user_id:
        await require_mesh_access(node_id, user)
    return {"result": "ok"}
```

## Step 3: Write Unit Tests

See `references/test-patterns.md` for full patterns. Key rules:
- Import as `from src.api.maas.endpoints import mymod as mod`
- Use `monkeypatch.setattr(mod, "get_mesh", ...)` to mock registry
- Always pass `interface="bat0"` explicitly — FastAPI Query() objects are not strings in direct calls
- Use `UserContext(user_id="owner-1", plan="starter")` for auth
- Use `AsyncMock` for `run_health_checks`, `collect`, `run_cycle`; `MagicMock` for sync methods

```python
from src.api.maas.auth import UserContext
from src.api.maas.endpoints import mymod as mod

USER = UserContext(user_id="owner-1", plan="starter")

@pytest.mark.asyncio
async def test_my_action_returns_ok(monkeypatch):
    instance = SimpleNamespace(owner_id="owner-1")
    monkeypatch.setattr(mod, "get_mesh", lambda _id: instance)
    resp = await mod.my_action("node-1", user=USER)
    assert resp["result"] == "ok"
```

## Step 4: Register Ownership and Commit

**CRITICAL**: New files must be registered in `docs/team/swarm_ownership.json` BEFORE committing.

```bash
# 1. Add new files to codex-implementer's allow list in swarm_ownership.json
#    (edit docs/team/swarm_ownership.json)

# 2. Commit ownership update as lead-coordinator
SWARM_AGENT=lead-coordinator git add docs/team/swarm_ownership.json
SWARM_AGENT=lead-coordinator git commit -m "chore(swarm): add mymod to codex-implementer scope"

# 3. Commit the actual code as codex-implementer
SWARM_AGENT=codex-implementer git add src/api/maas/endpoints/mymod.py tests/unit/api/endpoints/test_mymod_unit.py
SWARM_AGENT=codex-implementer git commit -m "feat(maas): add mymod endpoint with unit tests"
```

See `references/swarm-ownership.md` for the full ownership map.

## Step 5: Validate

```bash
python3 -m pytest tests/unit/api/endpoints/test_{mymod}_unit.py --no-cov -q
```

All tests must pass before marking task complete.

## Common Patterns

**404 on missing mesh:**
```python
instance = get_mesh(mesh_id)
if instance is None:
    raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")
```

**Access control:**
```python
if instance.owner_id != user.user_id:
    await require_mesh_access(mesh_id, user)
```

**Global instance cache (for services like health monitors):**
```python
_monitors: Dict[str, Any] = {}

def get_monitor(node_id: str, interface: str = "bat0") -> Any:
    key = f"{node_id}:{interface}"
    if key not in _monitors:
        _monitors[key] = MyMonitor(node_id=node_id, interface=interface)
    return _monitors[key]
```

## References

- `references/swarm-ownership.md` — ownership map (which SWARM_AGENT commits what)
- `references/test-patterns.md` — unit test patterns for MaaS endpoints
