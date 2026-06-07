"""Legacy MaaS compatibility facade with bounded evidence.

This module keeps the historical ``src.api.maas_legacy`` public contract alive
while the implementation around it moves to modular v4 surfaces. The facade is
intentionally explicit: legacy calls may still return raw API data to callers,
but EventBus evidence must contain only hashes and aggregate summaries.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta
from threading import Lock
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import (
    cross_plane_claim_gate_metadata,
    readiness_cross_plane_claim_gate_metadata,
)
from src.api.maas.auth import get_current_user, require_permission, require_role
from src.api.maas.endpoints.compat import router as compat_router
from src.api.maas.endpoints.mesh import router as mesh_router
from src.api.maas.endpoints.nodes_legacy import router as nodes_legacy_router
from src.api.maas.models import (
    BillingWebhookRequest,
    BillingWebhookResponse,
    LegacyBillingResponse,
    MeshDeployRequest,
    MeshDeployResponse,
    MeshMetricsResponse,
    MeshStatusResponse,
    NodeApproveRequest,
    NodeApproveResponse,
    NodeHeartbeatRequest,
    NodeRegisterRequest,
    NodeRegisterResponse,
    NodeReissueTokenRequest,
    NodeReissueTokenResponse,
    NodeRevokeRequest,
    NodeRevokeResponse,
    PolicyRequest,
    PolicyResponse,
    ScaleRequest,
    TokenRotateResponse,
)
from src.api.maas.mesh_instance import MeshInstance
from src.api.maas.services import BillingService as ModularBillingService
from src.api.maas.services import UsageMeteringService as ModularUsageMeteringService
from src.api.maas_auth import get_current_user_from_maas
from src.api.maas_security import api_key_manager, oidc_validator, token_signer
from src.coordination.events import EventBus, EventType, get_event_bus
from src.database import (
    BillingWebhookEvent,
    MeshInstance as DBMeshInstance,
    User,
    get_db,
)
from src.security.hardware_enclave import AttestationService
from src.services.maas_auth_service import MaaSAuthService, find_user_by_api_key

try:  # Optional in local/dev environments.
    from src.security.ebpf_pqc_gateway import PQC_AVAILABLE
except Exception:  # pragma: no cover - depends on host optional deps.
    PQC_AVAILABLE = False

try:  # Historical readiness surface only checks callability.
    from src.security.pqc_identity import PQCNodeIdentity
except Exception:  # pragma: no cover - optional.
    PQCNodeIdentity = None


logger = logging.getLogger(__name__)

router = APIRouter(tags=["MaaS Legacy"])
router.include_router(compat_router)
router.include_router(mesh_router)
router.include_router(nodes_legacy_router)

_registry_lock = Lock()
_mesh_registry: Dict[str, Any] = {}
_pending_nodes: Dict[str, Dict[str, Dict[str, Any]]] = {}
_node_telemetry: Dict[str, Dict[str, Any]] = {}
_mesh_policies: Dict[str, List[Dict[str, Any]]] = {}
_mesh_audit_log: Dict[str, List[Dict[str, Any]]] = {}
_mesh_mapek_events: Dict[str, List[Dict[str, Any]]] = {}
_revoked_nodes: Dict[str, Dict[str, Dict[str, Any]]] = {}
_mesh_reissue_tokens: Dict[str, Dict[str, Dict[str, Any]]] = {}
_billing_webhook_results: Dict[str, Dict[str, Any]] = {}

_MAPEK_EVENT_BUFFER_SIZE = 100

PLAN_REQUEST_LIMITS = {
    "free": 1000,
    "starter": 10000,
    "pro": 1000000,
    "enterprise": 10000000,
}

_LEGACY_MESH_METRICS_CROSS_PLANE_CLAIMS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)


def _utc_now() -> datetime:
    return datetime.utcnow()


def _redacted_sha256_prefix(value: Optional[Any], *, length: int = 16) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def _event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    state = getattr(request, "state", None)
    injected = getattr(state, "event_bus", None)
    if injected is not None:
        return injected
    project_root = getattr(state, "event_project_root", None) or getattr(
        state, "project_root", "."
    )
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize legacy MaaS EventBus: %s", exc)
        return None


def _publish(
    request: Optional[Request],
    *,
    source_agent: str,
    payload: Dict[str, Any],
    priority: int = 6,
) -> Optional[str]:
    bus = _event_bus_from_request(request)
    if bus is None:
        return None
    safe_payload = {
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        **payload,
    }
    event = bus.publish(
        EventType.PIPELINE_STAGE_END,
        source_agent,
        safe_payload,
        priority=priority,
    )
    return event.event_id


def _duration_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 3)


def _owner_id(user: Any) -> Optional[str]:
    return str(getattr(user, "id", "")) or None


def _is_operator(user: Any) -> bool:
    return getattr(user, "role", None) in {"admin", "operator"}


class MeshProvisioner:
    """Small legacy provisioner backed by the in-process registry."""

    async def create(
        self,
        *,
        user: Any = None,
        name: str = "",
        nodes: int = 5,
        owner_id: Optional[str] = None,
        pqc_enabled: bool = True,
        obfuscation: str = "none",
        traffic_profile: str = "none",
        join_token_ttl_sec: int = 604800,
    ) -> MeshInstance:
        resolved_owner_id = owner_id or _owner_id(user) or "unknown"
        mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
        instance = MeshInstance(
            mesh_id=mesh_id,
            name=name,
            owner_id=resolved_owner_id,
            nodes=nodes,
            pqc_enabled=pqc_enabled,
            obfuscation=obfuscation,
            traffic_profile=traffic_profile,
            plan=getattr(user, "plan", "starter"),
        )
        instance.join_token = secrets.token_urlsafe(32)
        instance.join_token_ttl_sec = join_token_ttl_sec
        instance.join_token_issued_at = _utc_now()
        instance.join_token_expires_at = instance.join_token_issued_at + timedelta(
            seconds=join_token_ttl_sec
        )
        await instance.provision()
        with _registry_lock:
            _mesh_registry[mesh_id] = instance
        return instance

    async def terminate(self, mesh_id: str) -> bool:
        with _registry_lock:
            instance = _mesh_registry.get(mesh_id)
            if instance is None:
                return False
            if hasattr(instance, "terminate"):
                await instance.terminate()
            _mesh_registry.pop(mesh_id, None)
        return True

    def get(self, mesh_id: str) -> Optional[Any]:
        return _mesh_registry.get(mesh_id)

    def list_for_owner(self, owner_id: str) -> List[Any]:
        return [
            instance
            for instance in _mesh_registry.values()
            if str(getattr(instance, "owner_id", "")) == str(owner_id)
            and getattr(instance, "status", None) != "terminated"
        ]


class AuthService:
    def __init__(self) -> None:
        self._shared = MaaSAuthService(
            api_key_factory=lambda: secrets.token_urlsafe(32),
            default_plan="starter",
        )

    def register(self, db: Session, req: Any) -> User:
        return self._shared.register(db, req)

    def login(self, db: Session, req: Any) -> str:
        return self._shared.login(db, req)

    def rotate_api_key(self, db: Session, user: User) -> tuple[str, datetime]:
        return self._shared.rotate_api_key(db, user)


class BillingService(ModularBillingService):
    """Legacy billing facade methods expected by historical callers."""

    PLAN_RANK = {"free": 0, "starter": 1, "pro": 2, "enterprise": 3}
    LIMITS = {"free": 1, "starter": 5, "pro": 1000, "enterprise": 10000}
    ALIASES = {
        "basic": "starter",
        "premium": "pro",
        "business": "enterprise",
    }

    def normalize_plan(self, plan: Optional[str]) -> str:
        normalized = self.ALIASES.get(
            str(plan or "starter").lower(),
            str(plan or "starter").lower(),
        )
        if normalized == "free":
            return "starter"
        return normalized if normalized in self.PLAN_RANK else "starter"

    def plan_catalog(self) -> Dict[str, Dict[str, Any]]:
        return {
            plan: {"max_nodes": self.LIMITS[plan], "rank": self.PLAN_RANK[plan]}
            for plan in self.PLAN_RANK
        }

    def check_quota(
        self,
        user: Any,
        requested_nodes: int,
        requested_plan: Optional[str] = None,
    ) -> bool:
        user_plan = self.normalize_plan(getattr(user, "plan", "starter"))
        request_plan = self.normalize_plan(requested_plan or user_plan)
        user_limit = self.LIMITS[user_plan]
        if requested_nodes > user_limit:
            raise HTTPException(status_code=402, detail="Quota exceeded")
        if self.PLAN_RANK[request_plan] > self.PLAN_RANK[user_plan]:
            raise HTTPException(status_code=403, detail="Plan escalation blocked")
        limit = min(user_limit, self.LIMITS[request_plan])
        if requested_nodes > limit:
            raise HTTPException(status_code=402, detail="Quota exceeded")
        return True


class UsageMeteringService(ModularUsageMeteringService):
    """Legacy usage-metering API over local MeshInstance objects."""

    def get_mesh_usage(self, instance: Any) -> Dict[str, Any]:
        now = _utc_now()
        total_node_hours = 0.0
        nodes = []
        for node_id, node in (getattr(instance, "node_instances", {}) or {}).items():
            started_raw = node.get("started_at")
            try:
                started = (
                    datetime.fromisoformat(started_raw)
                    if isinstance(started_raw, str)
                    else getattr(instance, "created_at", now)
                )
            except ValueError:
                started = getattr(instance, "created_at", now)
            hours = max(0.0, (now - started).total_seconds() / 3600.0)
            total_node_hours += hours
            nodes.append({"node_id": node_id, "hours": round(hours, 4)})
        return {
            "mesh_id": getattr(instance, "mesh_id", None),
            "mesh_name": getattr(instance, "name", None),
            "status": getattr(instance, "status", "unknown"),
            "active_nodes": len(nodes),
            "total_node_hours": round(total_node_hours, 4),
            "billing_period_start": getattr(
                instance,
                "created_at",
                now,
            ).isoformat(),
            "billing_period_end": now.isoformat(),
            "nodes": nodes,
        }

    def get_account_usage(self, owner_id: str) -> Dict[str, Any]:
        meshes = [
            instance
            for instance in _mesh_registry.values()
            if str(getattr(instance, "owner_id", "")) == str(owner_id)
        ]
        total = 0.0
        summaries = []
        for instance in meshes:
            usage = self.get_mesh_usage(instance)
            total += float(usage.get("total_node_hours") or 0.0)
            summaries.append(
                {
                    "mesh_id": usage.get("mesh_id"),
                    "mesh_name": usage.get("mesh_name"),
                    "status": usage.get("status"),
                    "active_nodes": usage.get("active_nodes"),
                    "total_node_hours": usage.get("total_node_hours"),
                }
            )
        return {
            "owner_id": owner_id,
            "total_node_hours": round(total, 4),
            "mesh_count": len(meshes),
            "meshes": summaries,
            "generated_at": _utc_now().isoformat(),
        }


mesh_provisioner = MeshProvisioner()
billing_service = BillingService()
usage_metering_service = UsageMeteringService()
auth_service = AuthService()


def validate_customer(api_key: str, db: Session) -> User:
    user = find_user_by_api_key(db, api_key)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user


def _legacy_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "add", "commit", "rollback"))


def _legacy_registries_available() -> bool:
    surfaces = (
        _mesh_registry,
        _pending_nodes,
        _node_telemetry,
        _mesh_policies,
        _mesh_audit_log,
        _mesh_mapek_events,
        _revoked_nodes,
        _mesh_reissue_tokens,
    )
    return all(isinstance(surface, dict) for surface in surfaces) and all(
        callable(getattr(_registry_lock, attr, None))
        for attr in ("acquire", "release", "locked")
    )


def _legacy_services_available() -> bool:
    return (
        all(
            callable(getattr(mesh_provisioner, attr, None))
            for attr in ("create", "terminate", "get", "list_for_owner")
        )
        and all(
            callable(getattr(billing_service, attr, None))
            for attr in ("normalize_plan", "plan_catalog", "check_quota")
        )
        and all(
            callable(getattr(usage_metering_service, attr, None))
            for attr in ("get_mesh_usage", "get_account_usage")
        )
        and all(
            callable(getattr(auth_service, attr, None))
            for attr in ("register", "login", "rotate_api_key")
        )
    )


def _legacy_auth_dependencies_available() -> bool:
    return (
        callable(get_current_user_from_maas)
        and callable(get_current_user)
        and callable(require_permission)
        and callable(require_role)
        and callable(getattr(api_key_manager, "generate", None))
        and callable(getattr(oidc_validator, "get_config", None))
        and callable(getattr(oidc_validator, "validate", None))
    )


def _legacy_security_helpers_available() -> bool:
    return (
        callable(getattr(token_signer, "sign_token", None))
        and callable(getattr(AttestationService, "validate_node", None))
        and (not PQC_AVAILABLE or callable(PQCNodeIdentity))
    )


def _legacy_db_models_available() -> bool:
    required = (
        (User, ("id", "email", "api_key_hash", "plan", "role")),
        (
            BillingWebhookEvent,
            ("event_id", "event_type", "payload_hash", "status", "created_at"),
        ),
        (DBMeshInstance, ("id", "name", "owner_id", "status", "plan", "created_at")),
    )
    return all(hasattr(model, attr) for model, attrs in required for attr in attrs)


def _legacy_readiness_status(db: Any) -> Dict[str, Any]:
    legacy_db_ready = _legacy_db_session_available(db)
    legacy_registries_ready = _legacy_registries_available()
    legacy_services_ready = _legacy_services_available()
    legacy_auth_ready = _legacy_auth_dependencies_available()
    legacy_security_ready = _legacy_security_helpers_available()
    legacy_models_ready = _legacy_db_models_available()
    degraded = []
    if not legacy_db_ready:
        degraded.append("database")
    if not legacy_registries_ready:
        degraded.append("registries")
    if not legacy_services_ready:
        degraded.append("legacy_services")
    if not legacy_auth_ready:
        degraded.append("auth_dependencies")
    if not legacy_security_ready:
        degraded.append("security_helpers")
    if not legacy_models_ready:
        degraded.append("db_models")
    return {
        "status": "ready" if not degraded else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "maas_legacy_runtime_ready": not degraded,
        "legacy_db_ready": legacy_db_ready,
        "legacy_registries_ready": legacy_registries_ready,
        "legacy_services_ready": legacy_services_ready,
        "legacy_auth_ready": legacy_auth_ready,
        "legacy_security_ready": legacy_security_ready,
        "legacy_models_ready": legacy_models_ready,
        "pqc_identity_available": PQC_AVAILABLE,
        "registry_counts": {
            "meshes": len(_mesh_registry) if isinstance(_mesh_registry, dict) else None,
            "pending_node_meshes": (
                len(_pending_nodes) if isinstance(_pending_nodes, dict) else None
            ),
            "telemetry_nodes": (
                len(_node_telemetry) if isinstance(_node_telemetry, dict) else None
            ),
            "revoked_node_meshes": (
                len(_revoked_nodes) if isinstance(_revoked_nodes, dict) else None
            ),
        },
        "route_precedence": {
            "fixed_prefix": "/api/v1/maas",
            "catch_all_owner": True,
            "known_shadowing_boundary": (
                "The legacy MaaS router exposes broad dynamic /{mesh_id}/... "
                "routes. Static readiness is registered explicitly so route "
                "availability is not confused with semantic mesh health."
            ),
        },
        "degraded_dependencies": degraded,
        "backing_state": {
            "database": "SQLAlchemy query/add/commit/rollback required.",
            "registries": "Legacy in-memory compatibility dictionaries required.",
            "legacy_services": "Provisioning, billing, usage, and auth services required.",
            "auth_dependencies": "MaaS auth dependencies and OIDC helpers required.",
            "security_helpers": "Token signer, attestation, and optional PQC helpers required.",
            "db_models": "User, BillingWebhookEvent, and MeshInstance model fields required.",
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_legacy_readiness"
        ),
        "claim_boundary": (
            "Legacy MaaS readiness proves route and local dependency surfaces "
            "are present. It does not deploy a mesh, validate dataplane traffic, "
            "prove customer traffic, or prove every dynamic /{mesh_id}/... route "
            "is semantically healthy."
        ),
    }


@router.get("/api/v1/maas/readiness")
async def maas_legacy_readiness(
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    payload = _legacy_readiness_status(db)
    degraded = set(payload.get("degraded_dependencies") or [])
    if degraded:
        setattr(request.state, "degraded_dependencies", degraded)
    return payload


legacy_maas_readiness = maas_legacy_readiness


def _get_from_modular_registry(mesh_id: str) -> Optional[Any]:
    try:
        from src.api.maas import registry as modular_registry

        getter = getattr(modular_registry, "get_mesh", None)
        if callable(getter):
            return getter(mesh_id)
    except Exception:
        return None
    return None


def _get_mesh_any(mesh_id: str) -> Optional[Any]:
    instance = None
    if callable(getattr(mesh_provisioner, "get", None)):
        instance = mesh_provisioner.get(mesh_id)
    return instance or _mesh_registry.get(mesh_id) or _get_from_modular_registry(mesh_id)


def _require_owner(mesh_id: str, current_user: Any) -> Any:
    instance = _get_mesh_any(mesh_id)
    if instance is None or str(getattr(instance, "owner_id", "")) != str(
        getattr(current_user, "id", "")
    ):
        raise HTTPException(status_code=404, detail="Mesh not found")
    return instance


def _get_mesh_or_404(mesh_id: str, owner_id: str) -> Any:
    return _require_owner(mesh_id, type("_User", (), {"id": owner_id})())


def _node_count(instance: Any) -> int:
    return len(getattr(instance, "node_instances", {}) or {})


def _healthy_node_count(instance: Any) -> int:
    return sum(
        1
        for node in (getattr(instance, "node_instances", {}) or {}).values()
        if node.get("status") == "healthy"
    )


async def deploy_mesh(
    req: MeshDeployRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    request: Optional[Request] = None,
) -> MeshDeployResponse:
    start = time.time()
    mesh_id = None
    join_token = None
    registry_mutated = False
    try:
        billing_service.check_quota(
            current_user,
            req.nodes,
            requested_plan=req.billing_plan,
        )
        instance = await mesh_provisioner.create(
            user=current_user,
            name=req.name,
            nodes=req.nodes,
            pqc_enabled=req.pqc_enabled,
            obfuscation=req.obfuscation,
            traffic_profile=req.traffic_profile,
            join_token_ttl_sec=req.join_token_ttl_sec,
        )
        mesh_id = instance.mesh_id
        join_token = getattr(instance, "join_token", None)
        _mesh_registry[mesh_id] = instance
        registry_mutated = True
        if hasattr(db, "add"):
            db.add(
                DBMeshInstance(
                    id=mesh_id,
                    name=req.name,
                    owner_id=getattr(current_user, "id", None),
                    plan=req.billing_plan,
                    nodes=req.nodes,
                    pqc_profile=getattr(instance, "pqc_profile", "edge"),
                    pqc_enabled=req.pqc_enabled,
                    obfuscation=req.obfuscation,
                    traffic_profile=req.traffic_profile,
                    join_token=join_token,
                    join_token_expires_at=getattr(
                        instance, "join_token_expires_at", None
                    ),
                    status=getattr(instance, "status", "active"),
                )
            )
        if hasattr(db, "commit"):
            db.commit()
        _publish_legacy_lifecycle_event(
            request,
            operation="legacy_mesh_deploy",
            stage="deployed",
            status="success",
            mesh_id=mesh_id,
            owner_id=getattr(current_user, "id", None),
            node_count=req.nodes,
            registry_mutated=registry_mutated,
            db_persisted=True,
            join_token_issued=bool(join_token),
            request_summary={
                "mesh_name_present": bool(req.name),
                "requested_nodes": req.nodes,
            },
            duration_ms=_duration_ms(start),
        )
        return MeshDeployResponse(
            mesh_id=mesh_id,
            join_config={"token": join_token, "ttl_sec": req.join_token_ttl_sec},
            dashboard_url=f"/dashboard/{mesh_id}",
            status=getattr(instance, "status", "active"),
            pqc_enabled=req.pqc_enabled,
            created_at=getattr(instance, "created_at", _utc_now()).isoformat(),
            plan=req.billing_plan,
            join_token_expires_at=getattr(
                instance, "join_token_expires_at", _utc_now()
            ).isoformat(),
        )
    except Exception as exc:
        if hasattr(db, "rollback"):
            db.rollback()
        if mesh_id:
            _mesh_registry.pop(mesh_id, None)
        _publish_legacy_lifecycle_event(
            request,
            operation="legacy_mesh_deploy",
            stage="db_persist_failed" if registry_mutated else "failed",
            status="failed",
            mesh_id=mesh_id,
            owner_id=getattr(current_user, "id", None),
            node_count=req.nodes,
            registry_mutated=registry_mutated,
            db_persisted=False,
            join_token_issued=bool(join_token),
            request_summary={
                "mesh_name_present": bool(req.name),
                "requested_nodes": req.nodes,
            },
            reason="db_persist_failed" if registry_mutated else type(exc).__name__,
            duration_ms=_duration_ms(start),
        )
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=500,
            detail="Database persistence error during mesh deployment",
        ) from exc


def _publish_legacy_lifecycle_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    mesh_id: Optional[Any],
    owner_id: Optional[Any] = None,
    node_count: int = 0,
    registry_mutated: bool = False,
    db_persisted: bool = False,
    join_token_issued: bool = False,
    request_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
    duration_ms: float = 0.0,
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-lifecycle",
        payload={
            "component": "api.maas_legacy",
            "operation": operation,
            "service_name": "maas-legacy-lifecycle",
            "source_alias": "maas-legacy-lifecycle",
            "layer": "api_legacy_lifecycle_control_action",
            "stage": stage,
            "status": status,
            "duration_ms": duration_ms,
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "node_count": node_count,
            "registry_mutated": registry_mutated,
            "db_persisted": db_persisted,
            "join_token_issued": join_token_issued,
            "request_summary": request_summary or {},
            "read_only": False,
            "control_action": True,
            "reason": reason,
        },
    )


def _publish_legacy_lifecycle_read_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    current_user: Any = None,
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    mesh_count: Optional[int] = None,
    node_count: Optional[int] = None,
    healthy_node_count: Optional[int] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-lifecycle-read",
        payload={
            "component": "api.maas_legacy",
            "operation": operation,
            "service_name": "maas-legacy-lifecycle-read",
            "source_alias": "maas-legacy-lifecycle-read",
            "layer": "api_legacy_lifecycle_observed_state",
            "stage": stage,
            "status": status,
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "actor_user_id_hash": _redacted_sha256_prefix(
                getattr(current_user, "id", None)
            ),
            "mesh_count": mesh_count,
            "node_count": node_count,
            "healthy_node_count": healthy_node_count,
            "result_summary": result_summary or {},
            "read_only": True,
            "observed_state": True,
            "control_action": False,
            "reason": reason,
        },
    )


async def legacy_list_meshes(
    request: Optional[Request] = None,
    current_user: User = Depends(get_current_user_from_maas),
) -> Dict[str, Any]:
    instances = mesh_provisioner.list_for_owner(getattr(current_user, "id", None))
    meshes = [
        {
            "mesh_id": instance.mesh_id,
            "name": getattr(instance, "name", ""),
            "status": getattr(instance, "status", "unknown"),
            "nodes": _node_count(instance),
        }
        for instance in instances
    ]
    _publish_legacy_lifecycle_read_event(
        request,
        operation="legacy_mesh_list_read",
        stage="list_read",
        status="success",
        current_user=current_user,
        owner_id=getattr(current_user, "id", None),
        mesh_count=len(meshes),
        node_count=sum(_node_count(instance) for instance in instances),
        healthy_node_count=sum(_healthy_node_count(instance) for instance in instances),
    )
    return {"count": len(meshes), "meshes": meshes}


async def legacy_mesh_status(
    mesh_id: str,
    request: Optional[Request] = None,
    current_user: User = Depends(get_current_user_from_maas),
) -> MeshStatusResponse:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_legacy_lifecycle_read_event(
            request,
            operation="legacy_mesh_status_read",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            reason="mesh_not_found_or_forbidden",
        )
        raise
    peers = [
        {"node_id": node_id, "status": node.get("status", "unknown")}
        for node_id, node in (getattr(instance, "node_instances", {}) or {}).items()
    ]
    response = MeshStatusResponse(
        mesh_id=mesh_id,
        status=getattr(instance, "status", "unknown"),
        nodes_total=len(peers),
        nodes_healthy=_healthy_node_count(instance),
        uptime_seconds=(
            instance.get_uptime() if callable(getattr(instance, "get_uptime", None)) else 0
        ),
        pqc_enabled=bool(getattr(instance, "pqc_enabled", False)),
        obfuscation=getattr(instance, "obfuscation", "none"),
        traffic_profile=getattr(instance, "traffic_profile", "none"),
        peers=peers,
        health_score=(
            instance.get_health_score()
            if callable(getattr(instance, "get_health_score", None))
            else 0
        ),
        mesh_lifecycle_claim_gate=_legacy_observed_claim_gate(
            surface="legacy_maas_mesh.status"
        ),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _LEGACY_MESH_METRICS_CROSS_PLANE_CLAIMS,
            surface="legacy_maas_mesh.status",
        ),
    )
    _publish_legacy_lifecycle_read_event(
        request,
        operation="legacy_mesh_status_read",
        stage="status_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        node_count=response.nodes_total,
        healthy_node_count=response.nodes_healthy,
        result_summary={"peer_count": len(peers)},
    )
    return response


def _legacy_observed_claim_gate(*, surface: str) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.legacy_observed_claim_gate.v1",
        "surface": surface,
        "local_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }


def _legacy_mesh_metrics_claim_gate() -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.legacy_mesh_metrics_claim_gate.v1",
        "surface": "legacy_maas_mesh.metrics",
        "local_mesh_metrics_observation_claim_allowed": True,
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
    }


async def legacy_mesh_metrics(
    mesh_id: str,
    request: Optional[Request] = None,
    current_user: User = Depends(get_current_user_from_maas),
) -> MeshMetricsResponse:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_legacy_lifecycle_read_event(
            request,
            operation="legacy_mesh_metrics_read",
            stage="access_denied",
            status="denied",
            current_user=current_user,
            mesh_id=mesh_id,
            reason="mesh_not_found_or_forbidden",
        )
        raise
    response = MeshMetricsResponse(
        mesh_id=mesh_id,
        consciousness=instance.get_consciousness_metrics(),
        mape_k=instance.get_mape_k_state(),
        network=instance.get_network_metrics(),
        mesh_metrics_claim_gate=_legacy_mesh_metrics_claim_gate(),
        cross_plane_claim_gate=cross_plane_claim_gate_metadata(
            _LEGACY_MESH_METRICS_CROSS_PLANE_CLAIMS,
            surface="legacy_maas_mesh.metrics",
        ),
        timestamp=_utc_now().isoformat(),
    )
    _publish_legacy_lifecycle_read_event(
        request,
        operation="legacy_mesh_metrics_read",
        stage="metrics_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        result_summary={
            "consciousness_metric_count": len(response.consciousness),
            "mape_k_metric_count": len(response.mape_k),
            "network_metric_count": len(response.network),
            "mesh_metrics_claim_gate_present": True,
            "cross_plane_claim_gate_present": True,
            "production_readiness_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "external_dpi_bypass_claim_allowed": False,
            "has_timestamp": bool(response.timestamp),
        },
    )
    return response


def _heartbeat_summary(req: NodeHeartbeatRequest) -> Dict[str, Any]:
    pheromones = req.pheromones or {}
    return {
        "has_pheromones": bool(pheromones),
        "pheromone_destination_count": len(pheromones),
        "raw_metric_values_redacted": True,
        "payloads_redacted": True,
    }


def _publish_heartbeat_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    node_id: Optional[Any],
    mesh_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    actor_user_id: Optional[Any] = None,
    node_found: bool = False,
    owner_checked: bool = False,
    authorized: bool = False,
    stored_telemetry: bool = False,
    mapek_event_recorded: bool = False,
    reason: str = "",
    heartbeat_summary: Optional[Dict[str, Any]] = None,
    duration_ms: float = 0.0,
) -> Optional[str]:
    mesh_events = _mesh_mapek_events.get(str(mesh_id), []) if mesh_id else []
    return _publish(
        request,
        source_agent="maas-legacy-heartbeat",
        payload={
            "component": "api.maas_legacy",
            "operation": "legacy_heartbeat",
            "service_name": "maas-legacy-heartbeat",
            "source_alias": "maas-legacy-heartbeat",
            "layer": "api_legacy_heartbeat_observed_state",
            "stage": stage,
            "status": status,
            "duration_ms": duration_ms,
            "node_id_hash": _redacted_sha256_prefix(node_id),
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "actor_user_id_hash": _redacted_sha256_prefix(actor_user_id),
            "node_found": node_found,
            "owner_checked": owner_checked,
            "authorized": authorized,
            "stored_telemetry": stored_telemetry,
            "mapek_event_recorded": mapek_event_recorded,
            "heartbeat_summary": heartbeat_summary or {},
            "telemetry_store_summary": {
                "storage_backend": "legacy_in_memory",
                "mutation_attempted": stored_telemetry,
                "current_node_stored": node_id in _node_telemetry if node_id else False,
                "stored_nodes_total": len(_node_telemetry),
            },
            "mapek_store_summary": {
                "storage_backend": "legacy_in_memory",
                "mutation_attempted": mapek_event_recorded,
                "event_recorded": mapek_event_recorded,
                "mesh_event_count_after": len(mesh_events),
                "buffer_limit": _MAPEK_EVENT_BUFFER_SIZE,
                "event_type": "node.heartbeat" if mapek_event_recorded else None,
            },
            "storage_backend": "legacy_in_memory",
            "source_quality": (
                "legacy_in_memory_telemetry_and_mapek"
                if authorized
                else "denied_before_state_mutation"
            ),
            "dataplane_confirmed": False,
            "read_only": not authorized,
            "reason": reason,
        },
    )


def heartbeat(
    req: NodeHeartbeatRequest,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    start = time.time()
    actor_id = getattr(current_user, "id", None)
    found_mesh_id = None
    found_instance = None
    node_id = req.node_id
    for mesh_id, instance in _mesh_registry.items():
        if node_id in (getattr(instance, "node_instances", {}) or {}):
            found_mesh_id = mesh_id
            found_instance = instance
            break
    if found_instance is None:
        _publish_heartbeat_event(
            request,
            stage="denied",
            status="denied",
            node_id=node_id,
            node_found=False,
            authorized=False,
            reason="node_not_found",
            duration_ms=_duration_ms(start),
        )
        raise HTTPException(status_code=404, detail="Node not found")
    owner_id = getattr(found_instance, "owner_id", None)
    if str(owner_id) != str(actor_id):
        _publish_heartbeat_event(
            request,
            stage="denied",
            status="denied",
            node_id=node_id,
            mesh_id=found_mesh_id,
            owner_id=owner_id,
            actor_user_id=actor_id,
            node_found=True,
            owner_checked=True,
            authorized=False,
            reason="owner_mismatch",
            duration_ms=_duration_ms(start),
        )
        raise HTTPException(status_code=404, detail="Node not found")

    _node_telemetry[node_id] = {
        "status": req.status,
        "cpu_usage": req.cpu_usage,
        "memory_usage": req.memory_usage,
        "neighbors_count": req.neighbors_count,
        "routing_table_size": req.routing_table_size,
        "uptime": req.uptime,
        "updated_at": _utc_now().isoformat(),
    }
    event = {
        "node_id": node_id,
        "phase": "MONITOR",
        "event_type": "node.heartbeat",
        "cpu_usage": req.cpu_usage,
        "memory_usage": req.memory_usage,
        "timestamp": _utc_now().isoformat(),
    }
    events = _mesh_mapek_events.setdefault(found_mesh_id, [])
    events.append(event)
    del events[:-_MAPEK_EVENT_BUFFER_SIZE]
    _publish_heartbeat_event(
        request,
        stage="accepted",
        status="success",
        node_id=node_id,
        mesh_id=found_mesh_id,
        owner_id=owner_id,
        actor_user_id=actor_id,
        node_found=True,
        owner_checked=True,
        authorized=True,
        stored_telemetry=True,
        mapek_event_recorded=True,
        heartbeat_summary=_heartbeat_summary(req),
        duration_ms=_duration_ms(start),
    )
    return {"status": "ack", "mesh_id": found_mesh_id, "event_emitted": True}


def _publish_billing_usage_event(
    request: Optional[Request],
    *,
    scope: str,
    owner_id: Optional[Any],
    mesh_id: Optional[Any] = None,
    usage: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    usage = usage or {}
    nodes = usage.get("nodes") if isinstance(usage.get("nodes"), list) else []
    meshes = usage.get("meshes") if isinstance(usage.get("meshes"), list) else []
    summary = (
        {
            "active_nodes": usage.get("active_nodes"),
            "node_entries": len(nodes),
        }
        if scope == "mesh"
        else {
            "mesh_count": usage.get("mesh_count"),
            "mesh_entries": len(meshes),
        }
    )
    return _publish(
        request,
        source_agent="maas-legacy-billing-usage",
        payload={
            "component": "api.maas_legacy",
            "operation": "billing_usage_read",
            "service_name": "maas-billing",
            "source_alias": "maas-legacy-billing-usage",
            "layer": "billing_usage_observed_state",
            "stage": "usage_read",
            "status": "success",
            "scope": scope,
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "usage_summary": summary,
            "observed_state": True,
            "read_only": True,
            "safe_actuator": False,
        },
    )


async def legacy_mesh_usage(
    mesh_id: str,
    request: Optional[Request] = None,
    current_user: User = Depends(get_current_user_from_maas),
) -> Dict[str, Any]:
    instance = _get_mesh_or_404(mesh_id, getattr(current_user, "id", None))
    usage = usage_metering_service.get_mesh_usage(instance)
    _publish_billing_usage_event(
        request,
        scope="mesh",
        owner_id=getattr(current_user, "id", None),
        mesh_id=mesh_id,
        usage=usage,
    )
    return usage


async def legacy_account_usage(
    request: Optional[Request] = None,
    current_user: User = Depends(get_current_user_from_maas),
) -> Dict[str, Any]:
    usage = usage_metering_service.get_account_usage(getattr(current_user, "id", None))
    _publish_billing_usage_event(
        request,
        scope="account",
        owner_id=getattr(current_user, "id", None),
        usage=usage,
    )
    return usage


async def legacy_billing_webhook(
    req: BillingWebhookRequest,
    request: Request,
    db: Session = Depends(get_db),
    x_billing_webhook_secret: Optional[str] = None,
    x_billing_timestamp: Optional[str] = None,
    x_billing_signature: Optional[str] = None,
) -> Dict[str, Any]:
    raw_payload = await request.body()
    event_id = req.event_id or _redacted_sha256_prefix(raw_payload, length=32)
    payload_hash = hashlib.sha256(raw_payload).hexdigest()
    if event_id in _billing_webhook_results:
        cached = dict(_billing_webhook_results[event_id])
        _publish_legacy_billing_webhook_event(
            request,
            stage="idempotent_replay",
            status="replayed",
            req=req,
            event_id=event_id,
            payload_hash=payload_hash,
            user_id=cached.get("user_id"),
            plan_before=cached.get("plan_before"),
            plan_after=cached.get("plan_after"),
            idempotent_replay=True,
        )
        cached["idempotent_replay"] = True
        return cached

    user = None
    if req.user_id and hasattr(db, "query"):
        user = db.query(User).filter(User.id == req.user_id).first()
    if user is None and req.email and hasattr(db, "query"):
        user = db.query(User).filter(User.email == req.email).first()
    if user is None:
        _publish_legacy_billing_webhook_event(
            request,
            stage="failed",
            status="failed",
            req=req,
            event_id=event_id,
            payload_hash=payload_hash,
            user_id=req.user_id,
            reason="user_not_found",
        )
        raise HTTPException(status_code=404, detail="Billing user not found")

    plan_before = billing_service.normalize_plan(getattr(user, "plan", "starter"))
    if req.event_type in {"subscription.canceled", "subscription.deleted"}:
        plan_after = "starter"
    else:
        plan_after = billing_service.normalize_plan(req.plan or plan_before)
    user.plan = plan_after
    if req.customer_id:
        user.stripe_customer_id = req.customer_id
    if req.subscription_id:
        user.stripe_subscription_id = req.subscription_id
    if hasattr(db, "commit"):
        db.commit()
    response = {
        "processed": True,
        "event_id": event_id,
        "event_type": req.event_type,
        "user_id": user.id,
        "plan_before": plan_before,
        "plan_after": plan_after,
        "requests_limit": PLAN_REQUEST_LIMITS.get(
            plan_after, PLAN_REQUEST_LIMITS["starter"]
        ),
        "idempotent_replay": False,
    }
    _billing_webhook_results[event_id] = dict(response)
    _publish_legacy_billing_webhook_event(
        request,
        stage="processed",
        status="success",
        req=req,
        event_id=event_id,
        payload_hash=payload_hash,
        user_id=user.id,
        plan_before=plan_before,
        plan_after=plan_after,
    )
    return response


def _publish_legacy_billing_webhook_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    req: BillingWebhookRequest,
    event_id: str,
    payload_hash: str,
    user_id: Optional[Any] = None,
    plan_before: Optional[str] = None,
    plan_after: Optional[str] = None,
    idempotent_replay: bool = False,
    reason: str = "",
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-billing",
        payload={
            "component": "api.maas_legacy",
            "operation": "billing_webhook",
            "service_name": "maas-legacy-billing",
            "source_alias": "maas-legacy-billing",
            "layer": "api_legacy_billing_webhook_lifecycle",
            "stage": stage,
            "status": status,
            "event_type": req.event_type,
            "billing_event_id_hash": _redacted_sha256_prefix(event_id),
            "payload_hash_prefix": payload_hash[:16],
            "customer_id_hash": _redacted_sha256_prefix(req.customer_id),
            "subscription_id_hash": _redacted_sha256_prefix(req.subscription_id),
            "email_hash": _redacted_sha256_prefix(req.email),
            "user_id_hash": _redacted_sha256_prefix(user_id),
            "plan_before": plan_before,
            "plan_after": plan_after,
            "idempotent_replay": idempotent_replay,
            "reason": reason,
            "read_only": False,
            "control_action": True,
        },
    )


def _publish_node_lifecycle_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    mesh_id: Optional[Any],
    node_id: Optional[Any] = None,
    owner_id: Optional[Any] = None,
    actor_user_id: Optional[Any] = None,
    request_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
    **flags: Any,
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-node-lifecycle",
        payload={
            "component": "api.maas_legacy",
            "operation": operation,
            "service_name": "maas-legacy-node-lifecycle",
            "source_alias": "maas-legacy-node-lifecycle",
            "layer": "api_legacy_node_lifecycle_control_action",
            "stage": stage,
            "status": status,
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "node_id_hash": _redacted_sha256_prefix(node_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "actor_user_id_hash": _redacted_sha256_prefix(actor_user_id),
            "request_summary": request_summary or {},
            "control_action": True,
            "read_only": False,
            "reason": reason,
            **flags,
        },
    )


def _audit(mesh_id: str, *args: Any) -> None:
    """Append a legacy in-memory audit entry.

    EventBus evidence remains redacted elsewhere. This helper preserves the old
    local registry API, where direct callers can inspect raw in-process details.
    """

    if len(args) == 1 and isinstance(args[0], dict):
        record = args[0]
        entry = {
            "actor": record.get("actor"),
            "event": record.get("event"),
            "details": record.get("details"),
            "node_id_hash": _redacted_sha256_prefix(record.get("node_id")),
            "created_at": _utc_now().isoformat(),
        }
    elif len(args) == 3:
        actor, event, details = args
        entry = {
            "actor": actor,
            "event": event,
            "details": details,
            "created_at": _utc_now().isoformat(),
        }
    else:
        entry = {"event": "unknown", "created_at": _utc_now().isoformat()}
    _mesh_audit_log.setdefault(mesh_id, []).append(entry)


async def register_node(
    mesh_id: str,
    req: NodeRegisterRequest,
    request: Optional[Request] = None,
) -> NodeRegisterResponse:
    instance = _get_mesh_any(mesh_id)
    node_id = req.node_id or f"node-{uuid.uuid4().hex[:8]}"
    main_token_valid = (
        instance is not None
        and req.enrollment_token == getattr(instance, "join_token", None)
        and not _is_join_token_expired(instance)
    )
    reissue = (_mesh_reissue_tokens.get(mesh_id, {}) or {}).get(node_id, {})
    reissue_token_valid = (
        isinstance(reissue, dict)
        and _redacted_sha256_prefix(req.enrollment_token) == reissue.get("token_hash")
        and not _is_reissue_token_expired(reissue)
    )
    expired_main_token = (
        instance is not None
        and req.enrollment_token == getattr(instance, "join_token", None)
        and _is_join_token_expired(instance)
    )
    if instance is None or not (main_token_valid or reissue_token_valid):
        _publish_node_lifecycle_event(
            request,
            operation="legacy_node_register",
            stage="registration_denied",
            status="denied",
            mesh_id=mesh_id,
            node_id=node_id,
            owner_id=getattr(instance, "owner_id", None),
            reason="invalid_enrollment_token",
            pending_registry_mutated=False,
        )
        detail = "Enrollment token expired" if expired_main_token else "Invalid enrollment token"
        raise HTTPException(status_code=401, detail=detail)
    if reissue_token_valid:
        (_mesh_reissue_tokens.get(mesh_id, {}) or {}).pop(node_id, None)
    pending = {
        "node_id": node_id,
        "device_class": req.device_class,
        "labels": dict(req.labels),
        "public_keys": dict(req.public_keys),
        "hardware_id": req.hardware_id,
        "attestation_data": req.attestation_data,
        "enclave_enabled": req.enclave_enabled,
    }
    _pending_nodes.setdefault(mesh_id, {})[node_id] = pending
    _audit(mesh_id, {"event": "node_register", "node_id": node_id})
    _publish_node_lifecycle_event(
        request,
        operation="legacy_node_register",
        stage="registration_pending",
        status="success",
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary={
            "device_class": req.device_class,
            "label_count": len(req.labels),
            "public_key_count": len(req.public_keys),
        },
        pending_registry_mutated=True,
        audit_recorded=True,
    )
    return NodeRegisterResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="pending_approval",
        message="Node registration pending approval",
    )


async def approve_node(
    mesh_id: str,
    node_id: str,
    req: NodeApproveRequest,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> NodeApproveResponse:
    instance = _require_owner(mesh_id, current_user)
    pending = _pending_nodes.get(mesh_id, {}).pop(node_id, None)
    if pending is None:
        raise HTTPException(status_code=404, detail="Pending node not found")
    token = secrets.token_urlsafe(32)
    signed = token_signer.sign_token(token, mesh_id)
    instance.node_instances[node_id] = {
        "status": "healthy",
        "device_class": pending.get("device_class"),
        "tags": list(req.tags),
        "acl_profile": req.acl_profile,
        "pqc_profile": _get_pqc_profile(pending.get("device_class", "edge")),
    }
    _audit(mesh_id, {"event": "node_approve", "node_id": node_id})
    _publish_node_lifecycle_event(
        request,
        operation="legacy_node_approve",
        stage="approved",
        status="success",
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary={
            "acl_profile": req.acl_profile,
            "tag_count": len(req.tags),
            "pending_device_class": pending.get("device_class"),
        },
        node_registry_mutated=True,
        pending_registry_mutated=True,
        join_token_issued=True,
        audit_recorded=True,
    )
    return NodeApproveResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="approved",
        join_token=signed,
        approved_at=_utc_now().isoformat(),
    )


async def revoke_node(
    mesh_id: str,
    node_id: str,
    req: NodeRevokeRequest,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> NodeRevokeResponse:
    instance = _require_owner(mesh_id, current_user)
    node = (getattr(instance, "node_instances", {}) or {}).setdefault(node_id, {})
    node["status"] = "revoked"
    _revoked_nodes.setdefault(mesh_id, {})[node_id] = {
        "reason_length": len(req.reason),
        "revoked_at": _utc_now().isoformat(),
    }
    _audit(mesh_id, {"event": "node_revoke", "node_id": node_id})
    _publish_node_lifecycle_event(
        request,
        operation="legacy_node_revoke",
        stage="revoked",
        status="success",
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary={"reason_length": len(req.reason)},
        node_registry_mutated=True,
        revoked_registry_mutated=True,
        audit_recorded=True,
    )
    return NodeRevokeResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        status="revoked",
        reason=req.reason,
        revoked_at=_utc_now().isoformat(),
    )


async def reissue_node_token(
    mesh_id: str,
    node_id: str,
    req: NodeReissueTokenRequest,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> NodeReissueTokenResponse:
    instance = _require_owner(mesh_id, current_user)
    token = secrets.token_urlsafe(32)
    signed = token_signer.sign_token(token, mesh_id)
    issued = _utc_now()
    expires = issued + timedelta(seconds=req.ttl_seconds)
    _mesh_reissue_tokens.setdefault(mesh_id, {})[node_id] = {
        "token_hash": _redacted_sha256_prefix(token),
        "expires_at": expires.isoformat(),
    }
    _audit(mesh_id, {"event": "node_reissue", "node_id": node_id})
    _publish_node_lifecycle_event(
        request,
        operation="legacy_node_reissue_token",
        stage="reissue_token_issued",
        status="success",
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary={"ttl_seconds": req.ttl_seconds},
        reissue_token_mutated=True,
        join_token_issued=True,
        audit_recorded=True,
    )
    return NodeReissueTokenResponse(
        mesh_id=mesh_id,
        node_id=node_id,
        join_token=signed,
        issued_at=issued.isoformat(),
        expires_at=expires.isoformat(),
    )


def _publish_node_read_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    mesh_id: Optional[Any],
    owner_id: Optional[Any] = None,
    actor_user_id: Optional[Any] = None,
    node_status_filter: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-node-read",
        payload={
            "component": "api.maas_legacy",
            "operation": operation,
            "service_name": "maas-legacy-node-read",
            "source_alias": "maas-legacy-node-read",
            "layer": "api_legacy_node_observed_state",
            "stage": stage,
            "status": status,
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "actor_user_id_hash": _redacted_sha256_prefix(actor_user_id),
            "node_status_filter": node_status_filter,
            "result_summary": result_summary or {},
            "read_only": True,
            "control_action": False,
            "reason": reason,
        },
    )


def _node_summary(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    by_device: Dict[str, int] = {}
    tags = 0
    for node in nodes:
        status = node.get("status")
        by_status[status] = by_status.get(status, 0) + 1
        device = node.get("device_class")
        if device:
            by_device[device] = by_device.get(device, 0) + 1
        tags += len(node.get("tags") or [])
    summary = {
        "node_count": len(nodes),
        "by_status": by_status,
        "tag_entry_count": tags,
    }
    if by_device:
        summary["by_device_class"] = by_device
    return summary


def list_pending_nodes(
    mesh_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    if not _is_operator(current_user):
        _publish_node_read_event(
            request,
            operation="legacy_pending_node_list_read",
            stage="role_denied",
            status="denied",
            mesh_id=mesh_id,
            actor_user_id=getattr(current_user, "id", None),
            reason="operator_role_required",
        )
        raise HTTPException(status_code=403, detail="Operator role required")
    instance = _require_owner(mesh_id, current_user)
    nodes = [
        {"node_id": node_id, "status": "pending", **data}
        for node_id, data in (_pending_nodes.get(mesh_id, {}) or {}).items()
    ]
    _publish_node_read_event(
        request,
        operation="legacy_pending_node_list_read",
        stage="pending_node_list_read",
        status="success",
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        node_status_filter="pending",
        result_summary=_node_summary(nodes),
    )
    return {"pending": [node["node_id"] for node in nodes], "nodes": nodes}


def list_all_nodes(
    mesh_id: str,
    node_status: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    instance = _require_owner(mesh_id, current_user)
    nodes: List[Dict[str, Any]] = []
    for node_id, node in (getattr(instance, "node_instances", {}) or {}).items():
        status = "revoked" if node.get("status") == "revoked" else "approved"
        nodes.append({"node_id": node_id, "status": status, **node})
        nodes[-1]["status"] = status
    for node_id, node in (_pending_nodes.get(mesh_id, {}) or {}).items():
        nodes.append({"node_id": node_id, "status": "pending", **node})
    if node_status:
        nodes = [node for node in nodes if node.get("status") == node_status]
    summary = _node_summary(nodes)
    _publish_node_read_event(
        request,
        operation="legacy_node_list_read",
        stage="node_list_read",
        status="success",
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        result_summary=summary,
    )
    return {"nodes": nodes, "by_status": summary["by_status"]}


def _publish_token_lifecycle_event(
    request: Optional[Request],
    *,
    mesh_id: str,
    owner_id: Optional[Any],
    request_summary: Dict[str, Any],
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-token-lifecycle",
        payload={
            "component": "api.maas_legacy",
            "operation": "legacy_join_token_rotate",
            "service_name": "maas-legacy-token-lifecycle",
            "source_alias": "maas-legacy-token-lifecycle",
            "layer": "api_legacy_token_lifecycle_control_action",
            "stage": "rotated",
            "status": "success",
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "request_summary": request_summary,
            "token_rotated": True,
            "join_token_issued": True,
            "control_action": True,
            "read_only": False,
        },
    )


def rotate_join_token(
    mesh_id: str,
    ttl_seconds: int = 604800,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> TokenRotateResponse:
    instance = _require_owner(mesh_id, current_user)
    issued = _utc_now()
    expires = issued + timedelta(seconds=ttl_seconds)
    token = secrets.token_urlsafe(32)
    instance.join_token = token
    instance.join_token_issued_at = issued
    instance.join_token_expires_at = expires
    instance.join_token_ttl_sec = ttl_seconds
    _publish_token_lifecycle_event(
        request,
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary={"ttl_seconds": ttl_seconds},
    )
    return TokenRotateResponse(
        mesh_id=mesh_id,
        join_token=token,
        issued_at=issued.isoformat(),
        expires_at=expires.isoformat(),
    )


def _publish_policy_lifecycle_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    mesh_id: str,
    owner_id: Optional[Any] = None,
    actor_user_id: Optional[Any] = None,
    request_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
    **flags: Any,
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-policy-lifecycle",
        payload={
            "component": "api.maas_legacy",
            "operation": operation,
            "service_name": "maas-legacy-policy-lifecycle",
            "source_alias": "maas-legacy-policy-lifecycle",
            "layer": "api_legacy_policy_lifecycle_control_action",
            "stage": stage,
            "status": status,
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "actor_user_id_hash": _redacted_sha256_prefix(actor_user_id),
            "request_summary": request_summary or {},
            "control_action": True,
            "read_only": False,
            "reason": reason,
            **flags,
        },
    )


async def create_policy(
    mesh_id: str,
    req: PolicyRequest,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> PolicyResponse:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_policy_lifecycle_event(
            request,
            operation="legacy_policy_create",
            stage="access_denied",
            status="denied",
            mesh_id=mesh_id,
            actor_user_id=getattr(current_user, "id", None),
            request_summary={
                "source_tag_hash": _redacted_sha256_prefix(req.source_tag),
                "target_tag_hash": _redacted_sha256_prefix(req.target_tag),
                "action": req.action,
            },
            policy_registry_mutated=False,
            reason="mesh_not_found_or_forbidden",
        )
        raise
    policy_id = f"policy-{uuid.uuid4().hex[:8]}"
    row = {
        "id": policy_id,
        "source_tag": req.source_tag,
        "target_tag": req.target_tag,
        "action": req.action,
        "created_at": _utc_now().isoformat(),
    }
    _mesh_policies.setdefault(mesh_id, []).append(row)
    _audit(mesh_id, {"event": "policy_create", "node_id": policy_id})
    _publish_policy_lifecycle_event(
        request,
        operation="legacy_policy_create",
        stage="created",
        status="success",
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        request_summary={
            "policy_id_hash": _redacted_sha256_prefix(policy_id),
            "source_tag_hash": _redacted_sha256_prefix(req.source_tag),
            "target_tag_hash": _redacted_sha256_prefix(req.target_tag),
            "action": req.action,
        },
        policy_registry_mutated=True,
        audit_recorded=True,
    )
    return PolicyResponse(
        policy_id=policy_id,
        source_tag=req.source_tag,
        target_tag=req.target_tag,
        action=req.action,
        created_at=row["created_at"],
    )


def _publish_policy_read_event(
    request: Optional[Request],
    *,
    operation: str,
    stage: str,
    status: str,
    mesh_id: str,
    owner_id: Optional[Any] = None,
    actor_user_id: Optional[Any] = None,
    node_id: Optional[Any] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-policy-read",
        payload={
            "component": "api.maas_legacy",
            "operation": operation,
            "service_name": "maas-legacy-policy-read",
            "source_alias": "maas-legacy-policy-read",
            "layer": "api_legacy_policy_observed_state",
            "stage": stage,
            "status": status,
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "node_id_hash": _redacted_sha256_prefix(node_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "actor_user_id_hash": _redacted_sha256_prefix(actor_user_id),
            "result_summary": result_summary or {},
            "read_only": True,
            "control_action": False,
            "reason": reason,
        },
    )


async def legacy_list_policies_route(
    mesh_id: str,
    request: Optional[Request] = None,
    current_user: User = Depends(get_current_user_from_maas),
) -> Dict[str, Any]:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException:
        _publish_policy_read_event(
            request,
            operation="legacy_policy_list_read",
            stage="access_denied",
            status="denied",
            mesh_id=mesh_id,
            actor_user_id=getattr(current_user, "id", None),
            reason="mesh_not_found_or_forbidden",
        )
        raise
    policies = list(_mesh_policies.get(mesh_id, []))
    action_counts: Dict[str, int] = {}
    for policy in policies:
        action = policy.get("action")
        action_counts[action] = action_counts.get(action, 0) + 1
    _publish_policy_read_event(
        request,
        operation="legacy_policy_list_read",
        stage="policy_list_read",
        status="success",
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        result_summary={
            "policy_count": len(policies),
            "action_counts": action_counts,
        },
    )
    return {"policies": policies}


def get_node_config(
    mesh_id: str,
    node_id: str,
    request: Optional[Request] = None,
    current_user: User = Depends(get_current_user_from_maas),
) -> Dict[str, Any]:
    if hasattr(current_user, "id"):
        instance = _require_owner(mesh_id, current_user)
    else:
        instance = _get_mesh_any(mesh_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="Mesh not found")
    nodes = getattr(instance, "node_instances", {}) or {}
    source = nodes.get(node_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Node not found")
    source_tags = set(source.get("tags") or [])
    policies = _mesh_policies.get(mesh_id, [])
    allowed: List[str] = []
    denied: List[str] = []
    decisions: Dict[str, Dict[str, Any]] = {}
    explicit = 0
    for peer_id, peer in nodes.items():
        if peer_id == node_id:
            continue
        peer_tags = set(peer.get("tags") or [])
        matched = next(
            (
                policy
                for policy in policies
                if policy.get("source_tag") in source_tags
                and policy.get("target_tag") in peer_tags
            ),
            None,
        )
        if matched is not None:
            explicit += 1
            action = matched.get("action", "deny")
            decisions[peer_id] = {
                "action": action,
                "policy_id": matched.get("id"),
            }
        else:
            action = "deny"
            decisions[peer_id] = {"action": action, "policy_id": None}
        if action == "allow":
            allowed.append(peer_id)
        else:
            denied.append(peer_id)
    _publish_policy_read_event(
        request,
        operation="legacy_node_config_read",
        stage="node_config_read",
        status="success",
        mesh_id=mesh_id,
        node_id=node_id,
        owner_id=getattr(instance, "owner_id", None),
        result_summary={
            "allowed_peer_count": len(allowed),
            "denied_peer_count": len(denied),
            "decision_count": len(decisions),
            "explicit_policy_decision_count": explicit,
        },
    )
    return {
        "mesh_id": mesh_id,
        "node_id": node_id,
        "allowed_peers": allowed,
        "denied_peers": denied,
        "policy_decisions": decisions,
    }


def list_mapek_events(
    mesh_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user_from_maas),
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    try:
        instance = _require_owner(mesh_id, current_user)
    except HTTPException as exc:
        _publish_mapek_read_event(
            request,
            stage="access_denied",
            status="denied",
            mesh_id=mesh_id,
            actor_user_id=getattr(current_user, "id", None),
            returned_event_count=0,
            reason=f"http_{exc.status_code}",
        )
        raise
    stored = _mesh_mapek_events.get(mesh_id, [])
    events = stored[-limit:]
    _publish_mapek_read_event(
        request,
        stage="mapek_event_list_read",
        status="success",
        mesh_id=mesh_id,
        owner_id=getattr(instance, "owner_id", None),
        stored_event_count=len(stored),
        returned_event_count=len(events),
        result_summary=_mapek_summary(events),
    )
    return {"mesh_id": mesh_id, "count": len(events), "events": events}


def _mapek_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    phase_counts: Dict[str, int] = {}
    event_type_counts: Dict[str, int] = {}
    metric_mentions = 0
    for event in events:
        phase = event.get("phase")
        phase_key = phase if phase in {"MONITOR", "ANALYZE", "PLAN", "EXECUTE"} else "other"
        phase_counts[phase_key] = phase_counts.get(phase_key, 0) + 1
        event_type = event.get("event_type")
        event_type_key = event_type if event_type in {"node.heartbeat"} else "other"
        event_type_counts[event_type_key] = event_type_counts.get(event_type_key, 0) + 1
        if any(key in event for key in ("cpu_usage", "memory_usage", "packet_loss")):
            metric_mentions += 1
    return {
        "phase_counts": phase_counts,
        "event_type_counts": event_type_counts,
        "node_id_mentions": sum(1 for event in events if event.get("node_id")),
        "known_metric_mentions": metric_mentions,
    }


def _publish_mapek_read_event(
    request: Optional[Request],
    *,
    stage: str,
    status: str,
    mesh_id: str,
    owner_id: Optional[Any] = None,
    actor_user_id: Optional[Any] = None,
    stored_event_count: int = 0,
    returned_event_count: int = 0,
    result_summary: Optional[Dict[str, Any]] = None,
    reason: str = "",
) -> Optional[str]:
    return _publish(
        request,
        source_agent="maas-legacy-mapek-read",
        payload={
            "component": "api.maas_legacy",
            "operation": "legacy_mapek_event_read",
            "service_name": "maas-legacy-mapek-read",
            "source_alias": "maas-legacy-mapek-read",
            "layer": "api_legacy_mapek_observed_state",
            "stage": stage,
            "status": status,
            "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
            "owner_id_hash": _redacted_sha256_prefix(owner_id),
            "actor_user_id_hash": _redacted_sha256_prefix(actor_user_id),
            "stored_event_count": stored_event_count,
            "returned_event_count": returned_event_count,
            "result_summary": result_summary or {},
            "read_only": True,
            "control_action": False,
            "reason": reason,
        },
    )


def _is_join_token_expired(instance: Any) -> bool:
    expires_at = getattr(instance, "join_token_expires_at", None)
    if not isinstance(expires_at, datetime):
        return True
    return expires_at <= _utc_now()


def _is_reissue_token_expired(record: Dict[str, Any]) -> bool:
    expires_at = record.get("expires_at") if isinstance(record, dict) else None
    if not isinstance(expires_at, str):
        return True
    try:
        return datetime.fromisoformat(expires_at) <= _utc_now()
    except ValueError:
        return True


def _env_int_clamped(name: str, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def _billing_webhook_tolerance_seconds() -> int:
    return _env_int_clamped(
        "X0T_BILLING_WEBHOOK_TOLERANCE_SEC",
        default=300,
        minimum=30,
        maximum=3600,
    )


def _billing_event_ttl_seconds() -> int:
    return _env_int_clamped(
        "X0T_BILLING_EVENT_TTL_SEC",
        default=86_400,
        minimum=300,
        maximum=2_592_000,
    )


def _verify_billing_webhook_secret(provided: Optional[str]) -> None:
    expected = os.getenv("X0T_BILLING_WEBHOOK_SECRET")
    if not expected:
        return None
    if not provided or not hmac.compare_digest(str(provided), expected):
        raise HTTPException(status_code=401, detail="Invalid billing webhook secret")
    return None


def _payload_sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _verify_billing_webhook_hmac(
    payload: bytes,
    timestamp: Optional[str],
    signature: Optional[str],
) -> None:
    secret = os.getenv("X0T_BILLING_WEBHOOK_HMAC_SECRET")
    if not secret:
        return None
    if not timestamp:
        raise HTTPException(status_code=401, detail="Missing billing timestamp")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing billing signature")
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid billing timestamp") from exc
    if abs(time.time() - ts) > _billing_webhook_tolerance_seconds():
        raise HTTPException(status_code=401, detail="Billing signature expired")
    raw_signature = signature.split("=", 1)[1] if signature.startswith("sha256=") else signature
    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(raw_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid billing signature")
    return None


def _extract_billing_event_id(req: BillingWebhookRequest) -> str:
    candidates = [
        req.event_id,
        (req.metadata or {}).get("event_id"),
        (req.metadata or {}).get("id"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    raise HTTPException(status_code=400, detail="Missing billing event id")


def _deserialize_billing_event_response(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _resolve_billing_user(db: Session, req: BillingWebhookRequest) -> Optional[User]:
    user_id = req.user_id or (req.metadata or {}).get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user is not None:
            return user
    if req.customer_id:
        user = db.query(User).filter(User.stripe_customer_id == req.customer_id).first()
        if user is not None:
            return user
    if req.email:
        return db.query(User).filter(User.email == req.email).first()
    return None


def _start_billing_event_processing(
    db: Session,
    event_id: str,
    event_type: str,
    payload_hash: str,
) -> Optional[Dict[str, Any]]:
    existing = db.query(BillingWebhookEvent).filter_by(event_id=event_id).first()
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise HTTPException(
                status_code=409,
                detail="Billing event payload hash mismatch",
            )
        if existing.status == "done":
            return _deserialize_billing_event_response(existing.response_json)
        if existing.status == "processing":
            raise HTTPException(
                status_code=409,
                detail="Billing event already being processed",
            )
        if existing.status == "failed":
            raise HTTPException(
                status_code=409,
                detail="Billing event previously failed",
            )
    db.add(
        BillingWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload_hash=payload_hash,
            status="processing",
        )
    )
    db.commit()
    return None


def _finalize_billing_event_processing(
    db: Session,
    event_id: str,
    response: Dict[str, Any],
) -> None:
    row = db.query(BillingWebhookEvent).filter_by(event_id=event_id).first()
    if row is None:
        raise RuntimeError("Billing event reservation missing")
    row.status = "done"
    row.response_json = json.dumps(response)
    row.last_error = None
    row.processed_at = _utc_now()
    db.commit()


def _fail_billing_event_processing(db: Session, event_id: str, error: str) -> None:
    row = db.query(BillingWebhookEvent).filter_by(event_id=event_id).first()
    if row is None:
        return None
    row.status = "failed"
    row.last_error = str(error or "")[:2000]
    row.processed_at = _utc_now()
    db.commit()
    return None


def _cleanup_expired_billing_events(db: Session) -> None:
    cutoff = _utc_now() - timedelta(seconds=_billing_event_ttl_seconds())
    rows = db.query(BillingWebhookEvent).filter(BillingWebhookEvent.created_at < cutoff).all()
    for row in rows:
        db.delete(row)
    db.commit()


def _rule_matches(
    source_tags: List[str],
    target_tags: List[str],
    source_tag: str,
    target_tag: str,
) -> bool:
    return source_tag in set(source_tags or []) and target_tag in set(target_tags or [])


def _evaluate_acl_decision(
    source_tags: List[str],
    target_tags: List[str],
    policies: List[Dict[str, Any]],
    acl_profile: str,
) -> Dict[str, Any]:
    if acl_profile == "isolated":
        return {"action": "deny", "reason": "acl_profile_isolated"}
    matched = [
        policy
        for policy in policies
        if _rule_matches(
            source_tags,
            target_tags,
            policy.get("source_tag"),
            policy.get("target_tag"),
        )
    ]
    if any(policy.get("action") == "deny" for policy in matched):
        return {"action": "deny", "reason": "explicit_deny"}
    allow = next((policy for policy in matched if policy.get("action") == "allow"), None)
    if allow is not None:
        return {"action": "allow", "reason": "explicit_allow", "policy_id": allow.get("id")}
    if not policies:
        return {"action": "allow", "reason": "legacy_open_mesh"}
    return {"action": "deny", "reason": "default_deny_zero_trust"}


def _find_mesh_id_for_node(node_id: str) -> Optional[str]:
    for mesh_id, instance in _mesh_registry.items():
        if node_id in (getattr(instance, "node_instances", {}) or {}):
            return mesh_id
    return None


def _build_mapek_heartbeat_event(telemetry: NodeHeartbeatRequest) -> Dict[str, Any]:
    cpu = float(telemetry.cpu_usage or telemetry.cpu_percent or 0.0)
    memory = float(telemetry.memory_usage or telemetry.memory_percent or 0.0)
    neighbors = int(telemetry.neighbors_count or 0)
    if neighbors == 0 or cpu >= 95.0 or memory >= 95.0:
        health_state = "critical"
        recommendation = "reroute_and_recover"
    elif cpu >= 85.0 or memory >= 85.0:
        health_state = "degraded"
        recommendation = "scale_or_rebalance"
    else:
        health_state = "healthy"
        recommendation = "maintain"
    return {
        "event_id": f"mapek-{uuid.uuid4().hex}",
        "timestamp": _utc_now().isoformat(),
        "phase": "MONITOR",
        "event_type": "node.heartbeat",
        "node_id": telemetry.node_id,
        "health_state": health_state,
        "recommendation": recommendation,
        "signals": {
            "cpu_usage": cpu,
            "memory_usage": memory,
            "neighbors_count": neighbors,
            "routing_table_size": telemetry.routing_table_size,
            "uptime": telemetry.uptime,
        },
    }


_PQC_DEFAULT_PROFILE = {
    "kem": "ML-KEM-768",
    "sig": "ML-DSA-65",
    "security_level": 3,
}

_PQC_PROFILES = {
    "sensor": {"kem": "ML-KEM-512", "sig": "ML-DSA-44", "security_level": 1},
    "edge": _PQC_DEFAULT_PROFILE,
    "robot": _PQC_DEFAULT_PROFILE,
    "drone": _PQC_DEFAULT_PROFILE,
    "gateway": {"kem": "ML-KEM-1024", "sig": "ML-DSA-87", "security_level": 5},
    "server": {"kem": "ML-KEM-1024", "sig": "ML-DSA-87", "security_level": 5},
}

PQC_SEGMENT_PROFILES = _PQC_PROFILES


def _get_pqc_profile(device_class: str) -> Dict[str, Any]:
    return dict(_PQC_PROFILES.get(device_class, _PQC_DEFAULT_PROFILE))


def get_onprem_profile(
    mesh_id: str,
    format: str = "json",
    current_user: User = Depends(get_current_user_from_maas),
) -> Dict[str, Any]:
    instance = _require_owner(mesh_id, current_user)
    agent_configs = {
        node_id: {
            "mesh_id": mesh_id,
            "node_id": node_id,
            "pqc_profile": node.get("pqc_profile")
            or _get_pqc_profile(node.get("device_class", "edge")),
        }
        for node_id, node in (getattr(instance, "node_instances", {}) or {}).items()
    }
    return {
        "schema_version": "1.0",
        "mesh_id": mesh_id,
        "format": format,
        "docker_compose": {
            "control-plane": {
                "image": "x0tta6bl4/control-plane:local",
                "environment": {"MESH_ID": mesh_id},
            },
            "services": {
                "control-plane": {
                    "image": "x0tta6bl4/control-plane:local",
                    "environment": {"MESH_ID": mesh_id},
                }
            }
        },
        "agent_configs": agent_configs,
        "join_token": getattr(instance, "join_token", None),
        "install_instructions": [
            "Deploy the control-plane service locally.",
            "Start mesh agents with the generated node configuration.",
        ],
        "claim_boundary": (
            "On-prem profile generation returns local configuration material. "
            "It does not prove deployment, node reachability, dataplane delivery, "
            "customer traffic, or production readiness."
        ),
    }


__all__ = [
    "router",
    "BillingWebhookRequest",
    "BillingWebhookResponse",
    "LegacyBillingResponse",
    "MeshDeployRequest",
    "MeshDeployResponse",
    "MeshStatusResponse",
    "MeshMetricsResponse",
    "MeshInstance",
    "MeshProvisioner",
    "NodeApproveRequest",
    "NodeApproveResponse",
    "NodeHeartbeatRequest",
    "NodeRegisterRequest",
    "NodeRegisterResponse",
    "NodeReissueTokenRequest",
    "NodeReissueTokenResponse",
    "NodeRevokeRequest",
    "NodeRevokeResponse",
    "PolicyRequest",
    "PolicyResponse",
    "ScaleRequest",
    "TokenRotateResponse",
    "BillingService",
    "UsageMeteringService",
    "PQC_SEGMENT_PROFILES",
    "_MAPEK_EVENT_BUFFER_SIZE",
    "_PQC_DEFAULT_PROFILE",
    "_audit",
    "_billing_event_ttl_seconds",
    "_billing_webhook_tolerance_seconds",
    "_build_mapek_heartbeat_event",
    "_cleanup_expired_billing_events",
    "_deserialize_billing_event_response",
    "_evaluate_acl_decision",
    "_extract_billing_event_id",
    "_fail_billing_event_processing",
    "_finalize_billing_event_processing",
    "_find_mesh_id_for_node",
    "_get_mesh_or_404",
    "_get_pqc_profile",
    "_is_join_token_expired",
    "_is_reissue_token_expired",
    "_mesh_audit_log",
    "_mesh_mapek_events",
    "_mesh_policies",
    "_mesh_registry",
    "_mesh_reissue_tokens",
    "_node_telemetry",
    "_pending_nodes",
    "_payload_sha256_hex",
    "_redacted_sha256_prefix",
    "_resolve_billing_user",
    "_revoked_nodes",
    "_rule_matches",
    "_start_billing_event_processing",
    "_verify_billing_webhook_hmac",
    "_verify_billing_webhook_secret",
    "auth_service",
    "billing_service",
    "create_policy",
    "deploy_mesh",
    "get_node_config",
    "get_onprem_profile",
    "heartbeat",
    "legacy_account_usage",
    "legacy_billing_webhook",
    "legacy_list_meshes",
    "legacy_list_policies_route",
    "legacy_maas_readiness",
    "legacy_mesh_metrics",
    "legacy_mesh_status",
    "legacy_mesh_usage",
    "list_all_nodes",
    "list_mapek_events",
    "list_pending_nodes",
    "maas_legacy_readiness",
    "mesh_provisioner",
    "register_node",
    "reissue_node_token",
    "revoke_node",
    "rotate_join_token",
    "usage_metering_service",
    "validate_customer",
]
