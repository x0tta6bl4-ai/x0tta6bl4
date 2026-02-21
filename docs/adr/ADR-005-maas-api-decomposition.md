# ADR-005: MaaS Legacy API Decomposition

## Status
Accepted

## Context
The `src/api/maas_legacy.py` file contains 2422 lines of code implementing the entire MaaS (Mesh-as-a-Service) API with multiple responsibilities, making it the largest "god-object" in the codebase.

### Current Structure Analysis

| Component | Lines | Responsibility |
|-----------|-------|----------------|
| Pydantic Models | ~200 | Request/Response schemas |
| Constants & Profiles | ~50 | PQC profiles, plan aliases |
| MeshInstance | ~150 | Mesh lifecycle & metrics |
| Global Registry | ~50 | In-memory state management |
| Services | ~200 | Billing, Provisioner, Usage, Auth |
| Auth Dependencies | ~100 | FastAPI dependencies |
| ACL Helpers | ~50 | Access control evaluation |
| Billing Webhook | ~200 | HMAC, idempotency, event processing |
| MAPE-K Helpers | ~50 | Event building |
| Auth Endpoints | ~100 | Register, login, API key |
| OIDC Endpoints | ~70 | SSO integration |
| Mesh Endpoints | ~200 | Deploy, list, status, scale, terminate |
| Node Endpoints | ~300 | Register, approve, revoke, reissue |
| Policy Endpoints | ~100 | ACL policy management |
| Billing Endpoints | ~150 | Usage, webhook |
| Dashboard Endpoints | ~50 | UI serving |

### Issues
1. **Testability**: Testing one endpoint requires loading all 2400+ lines
2. **Maintainability**: Changes to billing affect mesh endpoints
3. **Readability**: Understanding the API requires scrolling through many endpoints
4. **Team Scalability**: Multiple developers cannot work on different endpoints simultaneously

## Decision
Decompose `maas_legacy.py` into a package `src/api/maas/` with the following modules:

### Package Structure

```
src/api/maas/
├── __init__.py           # Router export
├── models.py             # Pydantic models (~200 lines)
├── constants.py          # PQC profiles, plan aliases (~50 lines)
├── mesh_instance.py      # MeshInstance class (~150 lines)
├── registry.py           # Global state management (~100 lines)
├── services.py           # Business services (~200 lines)
├── auth.py               # Auth dependencies (~100 lines)
├── acl.py                # ACL evaluation (~50 lines)
├── billing_helpers.py    # Webhook helpers (~200 lines)
├── mapek.py              # MAPE-K event helpers (~50 lines)
├── endpoints/
│   ├── __init__.py
│   ├── auth.py           # Auth endpoints (~100 lines)
│   ├── oidc.py           # OIDC endpoints (~70 lines)
│   ├── mesh.py           # Mesh lifecycle (~200 lines)
│   ├── nodes.py          # Node management (~300 lines)
│   ├── policies.py       # Policy management (~100 lines)
│   ├── billing.py        # Billing endpoints (~150 lines)
│   └── dashboard.py      # Dashboard/UI (~50 lines)
└── router.py             # Main router assembly (~50 lines)
```

### Module Responsibilities

#### `models.py`
- All Pydantic request/response models
- MeshDeployRequest, MeshDeployResponse
- NodeRegisterRequest, NodeRegisterResponse
- BillingWebhookRequest, BillingWebhookResponse
- PolicyRequest, PolicyResponse

#### `constants.py`
- PQC_SEGMENT_PROFILES
- PLAN_ALIASES
- BILLING_WEBHOOK_EVENTS
- PLAN_REQUEST_LIMITS

#### `mesh_instance.py`
- MeshInstance class
- Lifecycle methods (provision, terminate, scale)
- Metrics methods (health, consciousness, MAPE-K, network)

#### `registry.py`
- Global state dictionaries
- Registry lock management
- Audit logging helpers

#### `services.py`
- BillingService
- MeshProvisioner
- UsageMeteringService
- AuthService

#### `auth.py`
- get_current_user dependency
- validate_customer helper
- _get_mesh_or_404 helper

#### `acl.py`
- _rule_matches
- _evaluate_acl_decision

#### `billing_helpers.py`
- HMAC verification
- Idempotency management
- Event processing
- User resolution

#### `mapek.py`
- _find_mesh_id_for_node
- _build_mapek_heartbeat_event

#### `endpoints/auth.py`
- POST /register
- POST /login
- POST /api-key
- GET /me
- GET /plans
- GET /pqc/profiles

#### `endpoints/oidc.py`
- GET /auth/oidc/config
- POST /auth/oidc/exchange

#### `endpoints/mesh.py`
- POST /deploy
- GET /list
- GET /{mesh_id}/status
- GET /{mesh_id}/metrics
- POST /{mesh_id}/scale
- DELETE /{mesh_id}
- POST /heartbeat

#### `endpoints/nodes.py`
- POST /{mesh_id}/register-node
- GET /{mesh_id}/pending-nodes
- POST /{mesh_id}/approve-node/{node_id}
- POST /{mesh_id}/nodes/{node_id}/revoke
- POST /{mesh_id}/nodes/{node_id}/reissue-token
- GET /{mesh_id}/nodes
- GET /{mesh_id}/nodes/all
- GET /{mesh_id}/nodes/revoked
- GET /{mesh_id}/node-config/{node_id}
- GET /{mesh_id}/nodes/{node_id}/pqc-profile

#### `endpoints/policies.py`
- GET /{mesh_id}/policies
- POST /{mesh_id}/policies
- GET /{mesh_id}/audit-logs
- GET /{mesh_id}/audit-logs/export
- GET /{mesh_id}/mapek/events

#### `endpoints/billing.py`
- GET /billing/usage
- GET /billing/usage/{mesh_id}
- POST /billing/webhook
- POST /{mesh_id}/tokens/rotate
- GET /{mesh_id}/deploy/onprem

#### `endpoints/dashboard.py`
- GET /control-plane/pending-approvals
- GET /{mesh_id}/dashboard/pending-approvals
- GET /{mesh_id}/topology

### Backward Compatibility

The `__init__.py` will re-export the router:

```python
from .router import router

__all__ = ["router"]
```

Existing imports will continue to work:
```python
from src.api.maas_legacy import router  # Still works via re-export
```

## Consequences

### Positive
- **Single Responsibility**: Each module has one clear purpose
- **Testability**: Endpoints can be tested in isolation
- **Team Scalability**: Multiple developers can work on different endpoints
- **Readability**: Smaller files are easier to navigate
- **Maintainability**: Changes are localized to specific modules

### Negative
- **More Files**: 18 files instead of 1
- **Import Complexity**: More internal imports needed
- **Refactoring Risk**: Large change requires careful testing

### Mitigation
- Re-export router from `__init__.py`
- Maintain same URL paths
- Comprehensive test coverage before refactoring
- Incremental migration with feature flags

## Implementation Plan

1. Create package directory structure
2. Extract constants and models (no dependencies)
3. Extract MeshInstance class
4. Extract registry and services
5. Extract helpers (auth, acl, billing, mapek)
6. Create endpoints package
7. Migrate endpoints by domain
8. Create main router with includes
9. Update imports in main app
10. Run full test suite

## Related
- ADR-001: Telemetry Module Decomposition
- ADR-002: Meta Cognitive Decomposition
- ADR-003: Metrics Exporter Decomposition
- ADR-004: Mesh Router Decomposition

## References
- [FastAPI Larger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Single Responsibility Principle](https://en.wikipedia.org/wiki/Single-responsibility_principle)
