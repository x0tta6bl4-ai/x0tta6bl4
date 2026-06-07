#!/usr/bin/env python3
"""Run a local MaaS autonomous mesh runtime smoke test.

This verifier exercises the current in-process control-plane path:

auth/register -> mesh/deploy -> node/register -> node/approve -> heartbeat ->
heal -> service-trace evidence summary.

It is intentionally local and bounded. It uses a temporary SQLite database and a
synthetic healing backend, so a READY result proves API/control-plane wiring and
claim-gate propagation only. It does not prove external infrastructure,
customer traffic, production SLOs, VPN reachability, or production readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
import uuid
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.maas.endpoints import auth as auth_endpoint_mod
from src.api.maas.nodes import healing as healing_mod
from src.api.maas import registry as maas_registry
from src.coordination.events import EventBus, EventType
from src.core.app import app
from src.database import Base, MeshNode, get_db
from src.services.service_event_trace import event_trace_evidence_summary


SCHEMA = "x0tta6bl4.maas_autonomous_mesh_runtime_smoke.v1"
READY_DECISION = "MAAS_AUTONOMOUS_MESH_RUNTIME_SMOKE_READY"
BLOCKED_DECISION = "MAAS_AUTONOMOUS_MESH_RUNTIME_SMOKE_BLOCKED"
CLAIM_BOUNDARY = (
    "Local in-process smoke verifier only. It proves the MaaS API can register "
    "a user, deploy a local mesh, enroll and approve an agent-style node, accept "
    "a heartbeat with redacted dataplane probe target, surface a bounded "
    "post-heal dataplane revalidation, and classify the resulting service-trace "
    "evidence gate. It does not prove external infrastructure provisioning, "
    "real customer traffic, VPN availability, external DPI bypass, production "
    "SLOs, or production readiness."
)


class SmokeFailure(RuntimeError):
    """Expected verifier failure with a machine-readable report."""

    def __init__(self, message: str, report: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.report = dict(report)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _redacted_id(value: Any) -> dict[str, Any]:
    text = str(value or "")
    return {
        "present": bool(text),
        "sha256": _sha256_text(text) if text else None,
        "raw_value_redacted": True,
    }


def _safe_bool(mapping: Mapping[str, Any], key: str) -> bool:
    return mapping.get(key) is True


def _registry_snapshots() -> dict[str, dict[Any, Any]]:
    return {
        "mesh_registry": dict(maas_registry._mesh_registry),
        "pending_nodes": {k: dict(v) for k, v in maas_registry._pending_nodes.items()},
        "node_telemetry": dict(maas_registry._node_telemetry),
        "mesh_policies": {k: list(v) for k, v in maas_registry._mesh_policies.items()},
        "mesh_audit_log": {k: list(v) for k, v in maas_registry._mesh_audit_log.items()},
        "mesh_mapek_events": {
            k: list(v) for k, v in maas_registry._mesh_mapek_events.items()
        },
        "revoked_nodes": {
            k: dict(v) for k, v in maas_registry._revoked_nodes.items()
        },
        "mesh_reissue_tokens": {
            k: dict(v) for k, v in maas_registry._mesh_reissue_tokens.items()
        },
    }


def _clear_registry() -> None:
    maas_registry._mesh_registry.clear()
    maas_registry._pending_nodes.clear()
    maas_registry._node_telemetry.clear()
    maas_registry._mesh_policies.clear()
    maas_registry._mesh_audit_log.clear()
    maas_registry._mesh_mapek_events.clear()
    maas_registry._revoked_nodes.clear()
    maas_registry._mesh_reissue_tokens.clear()


def _restore_registry(snapshot: Mapping[str, Mapping[Any, Any]]) -> None:
    _clear_registry()
    maas_registry._mesh_registry.update(snapshot["mesh_registry"])
    maas_registry._pending_nodes.update(snapshot["pending_nodes"])
    maas_registry._node_telemetry.update(snapshot["node_telemetry"])
    maas_registry._mesh_policies.update(snapshot["mesh_policies"])
    maas_registry._mesh_audit_log.update(snapshot["mesh_audit_log"])
    maas_registry._mesh_mapek_events.update(snapshot["mesh_mapek_events"])
    maas_registry._revoked_nodes.update(snapshot["revoked_nodes"])
    maas_registry._mesh_reissue_tokens.update(snapshot["mesh_reissue_tokens"])


@contextmanager
def _isolated_test_client(db_path: Path) -> Iterator[tuple[TestClient, Any]]:
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    dependency_overrides_before = dict(app.dependency_overrides)
    registry_before = _registry_snapshots()
    user_store = getattr(auth_endpoint_mod, "_user_store", None)
    login_attempts = getattr(auth_endpoint_mod, "_LOGIN_ATTEMPTS", None)
    user_store_before = dict(user_store) if hasattr(user_store, "items") else None
    login_attempts_before = (
        {key: list(value) for key, value in login_attempts.items()}
        if hasattr(login_attempts, "items")
        else None
    )

    def override_get_db() -> Iterator[Any]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    _clear_registry()
    if user_store_before is not None and hasattr(user_store, "clear"):
        user_store.clear()
    if login_attempts_before is not None and hasattr(login_attempts, "clear"):
        login_attempts.clear()

    try:
        with TestClient(app) as client:
            yield client, testing_session
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(dependency_overrides_before)
        _restore_registry(registry_before)
        if user_store_before is not None and hasattr(user_store, "clear"):
            user_store.clear()
            if hasattr(user_store, "update"):
                user_store.update(user_store_before)
        if login_attempts_before is not None and hasattr(login_attempts, "clear"):
            login_attempts.clear()
            for key, values in login_attempts_before.items():
                login_attempts[key] = deque(values)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@contextmanager
def _synthetic_healing_backend(event_bus: EventBus) -> Iterator[None]:
    original_available = healing_mod.MESH_HEALING_AVAILABLE
    original_mode = getattr(healing_mod, "VerificationMode", None)
    original_manager = getattr(healing_mod, "MeshNetworkManager", None)
    original_get_event_bus = healing_mod.get_event_bus

    class FakeVerificationMode:
        FULL = "full"

    class FakeMeshNetworkManager:
        def __init__(self, **kwargs: Any) -> None:
            self.event_bus = kwargs.get("event_bus") or event_bus

        async def trigger_aggressive_healing(
            self,
            *,
            auto_restore_nodes: bool,
            verification_mode: str,
            post_action_dataplane_probe_target: str | None = None,
        ) -> int:
            if auto_restore_nodes is not True:
                raise AssertionError("auto_restore_nodes must be true")
            if verification_mode != "full":
                raise AssertionError("verification_mode must be full")
            if not post_action_dataplane_probe_target:
                raise AssertionError("post_action_dataplane_probe_target is required")

            probe_event = self.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                "bounded-dataplane-probe",
                {
                    "operation": "local_bounded_dataplane_probe",
                    "status": "success",
                    "target_hash": _sha256_text(post_action_dataplane_probe_target),
                    "raw_target_redacted": True,
                    "payloads_redacted": True,
                },
            )
            evidence = {
                "source_agents": ["bounded-dataplane-probe"],
                "event_ids": [probe_event.event_id],
                "event_ids_count": 1,
                "events_total": 1,
                "redacted": True,
            }
            claim_boundary = "bounded synthetic dataplane probe evidence only"
            claim_gate = {
                "schema": "x0tta6bl4.mesh_network_manager.healing_claim_gate.v1",
                "decision": "RESTORED_DATAPLANE_CLAIM_ALLOWED",
                "post_action_probe_enabled": True,
                "post_action_probe_target_present": True,
                "post_action_probe_attempted": True,
                "post_action_dataplane_revalidated": True,
                "dataplane_confirmed": True,
                "restored_dataplane_claim_allowed": True,
                "traffic_delivery_claim_allowed": False,
                "customer_traffic_claim_allowed": False,
                "external_reachability_claim_allowed": False,
                "production_slo_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "requires_post_action_dataplane_revalidation": True,
                "blockers": [],
                "evidence": evidence,
                "claim_boundary": claim_boundary,
                "redacted": True,
            }
            self.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                "mesh-network-manager",
                {
                    "operation": "trigger_aggressive_healing",
                    "status": "success",
                    "post_action_dataplane_revalidation": {
                        "probe_enabled": True,
                        "probe_target_present": True,
                        "probe_attempted": True,
                        "dataplane_confirmed": True,
                        "post_action_dataplane_revalidated": True,
                        "restored_dataplane_claim_allowed": True,
                        "claim_gate": claim_gate,
                        "evidence": evidence,
                        "claim_boundary": claim_boundary,
                        "redacted": True,
                    },
                    "claim_gate": claim_gate,
                    "payloads_redacted": True,
                },
            )
            return 1

    healing_mod.MESH_HEALING_AVAILABLE = True
    healing_mod.VerificationMode = FakeVerificationMode
    healing_mod.MeshNetworkManager = FakeMeshNetworkManager
    healing_mod.get_event_bus = lambda _project_root=".": event_bus
    try:
        yield
    finally:
        healing_mod.MESH_HEALING_AVAILABLE = original_available
        healing_mod.VerificationMode = original_mode
        healing_mod.MeshNetworkManager = original_manager
        healing_mod.get_event_bus = original_get_event_bus


def _stage(
    name: str,
    *,
    status_code: int | None = None,
    ok: bool = False,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "http_status_code": status_code,
        "details": dict(details or {}),
    }


def _post_json(
    client: TestClient,
    path: str,
    *,
    json_body: Mapping[str, Any],
    api_key: str | None = None,
):
    headers = {"X-API-Key": api_key} if api_key else None
    return client.post(path, json=dict(json_body), headers=headers)


def _require_response(
    report: dict[str, Any],
    *,
    stage_name: str,
    response: Any,
    expected_status: int,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ok = response.status_code == expected_status
    report["stages"].append(
        _stage(
            stage_name,
            status_code=response.status_code,
            ok=ok,
            details=details,
        )
    )
    if ok:
        return response.json()

    failure_report = {
        **report,
        "ready": False,
        "decision": BLOCKED_DECISION,
        "failure": {
            "stage": stage_name,
            "expected_status": expected_status,
            "actual_status": response.status_code,
            "response_preview": response.text[:500],
        },
    }
    raise SmokeFailure(f"{stage_name} failed", failure_report)


def _assert_ready_condition(
    report: dict[str, Any],
    *,
    name: str,
    ok: bool,
    details: Mapping[str, Any] | None = None,
) -> None:
    report["stages"].append(_stage(name, ok=ok, details=details))
    if ok:
        return
    failure_report = {
        **report,
        "ready": False,
        "decision": BLOCKED_DECISION,
        "failure": {"stage": name, "details": dict(details or {})},
    }
    raise SmokeFailure(f"{name} failed", failure_report)


def run_verification(
    *,
    event_project_root: str,
    db_path: str | None = None,
    dataplane_probe_target: str = "127.0.0.1",
) -> dict[str, Any]:
    started = time.monotonic()

    def finalize(result: dict[str, Any]) -> dict[str, Any]:
        result["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        return result

    event_root = Path(event_project_root)
    event_root.mkdir(parents=True, exist_ok=True)
    event_bus = EventBus(str(event_root))
    effective_db_path = Path(db_path) if db_path else event_root / "maas-smoke.db"
    email = f"smoke-{uuid.uuid4().hex}@test.local"
    password = f"smoke-{uuid.uuid4().hex}"
    node_id = f"agent-{uuid.uuid4().hex[:16]}"

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "decision": BLOCKED_DECISION,
        "ready": False,
        "duration_ms": None,
        "stages": [],
        "entities": {
            "user": {"present": False, "raw_value_redacted": True},
            "mesh": {"present": False, "raw_value_redacted": True},
            "node": {"present": False, "raw_value_redacted": True},
        },
        "dataplane_probe_target": {
            "sha256": _sha256_text(dataplane_probe_target),
            "raw_value_redacted": True,
            "loopback_lab_target": dataplane_probe_target
            in {"127.0.0.1", "::1", "localhost"},
        },
        "evidence_gates": {},
        "event_project_root": str(event_root),
        "database": {
            "temporary_sqlite": True,
            "path": str(effective_db_path),
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }

    try:
        with _isolated_test_client(effective_db_path) as (client, testing_session):
            with _synthetic_healing_backend(event_bus):
                register_body = _require_response(
                    report,
                    stage_name="auth_register",
                    response=_post_json(
                        client,
                        "/api/v1/maas/auth/register",
                        json_body={
                            "email": email,
                            "password": password,
                            "name": "Local Smoke",
                        },
                    ),
                    expected_status=200,
                    details={"api_key_returned": True, "raw_credentials_redacted": True},
                )
                api_key = str(register_body.get("access_token") or "")
                user_id = str(register_body.get("user_id") or "")
                report["entities"]["user"] = _redacted_id(user_id)
                _assert_ready_condition(
                    report,
                    name="hashed_api_key_auth_material_issued",
                    ok=bool(api_key and user_id),
                    details={"api_key_present": bool(api_key), "raw_api_key_redacted": True},
                )

                deploy_body = _require_response(
                    report,
                    stage_name="mesh_deploy",
                    response=_post_json(
                        client,
                        "/api/v1/maas/mesh/deploy",
                        json_body={
                            "name": "Autonomous Mesh Runtime Smoke",
                            "nodes": 1,
                            "billing_plan": "starter",
                            "pqc_enabled": True,
                            "join_token_ttl_sec": 3600,
                        },
                        api_key=api_key,
                    ),
                    expected_status=201,
                    details={"join_material_expected": True},
                )
                mesh_id = str(deploy_body.get("mesh_id") or "")
                join_config = deploy_body.get("join_config")
                join_token = ""
                if isinstance(join_config, dict):
                    join_token = str(
                        join_config.get("enrollment_token")
                        or join_config.get("token")
                        or ""
                    )
                report["entities"]["mesh"] = _redacted_id(mesh_id)
                deploy_gate = deploy_body.get("mesh_deploy_claim_gate", {})
                report["evidence_gates"]["mesh_deploy"] = {
                    "local_db_persistence_claim_allowed": _safe_bool(
                        deploy_gate, "local_db_persistence_claim_allowed"
                    ),
                    "external_node_deployment_claim_allowed": _safe_bool(
                        deploy_gate, "external_node_deployment_claim_allowed"
                    ),
                    "production_readiness_claim_allowed": _safe_bool(
                        deploy_gate, "production_readiness_claim_allowed"
                    ),
                }
                _assert_ready_condition(
                    report,
                    name="mesh_join_material_available",
                    ok=bool(mesh_id and join_token),
                    details={
                        "mesh_id_present": bool(mesh_id),
                        "join_token_present": bool(join_token),
                        "raw_join_token_redacted": True,
                    },
                )

                register_node_body = _require_response(
                    report,
                    stage_name="agent_node_register",
                    response=_post_json(
                        client,
                        f"/api/v1/maas/{mesh_id}/nodes/register",
                        json_body={
                            "node_id": node_id,
                            "enrollment_token": join_token,
                            "device_class": "edge",
                        },
                    ),
                    expected_status=200,
                    details={"uses_mesh_enrollment_token": True},
                )
                report["entities"]["node"] = _redacted_id(
                    register_node_body.get("node_id") or node_id
                )
                node_runtime_credential = str(register_node_body.get("api_key") or "")
                _assert_ready_condition(
                    report,
                    name="agent_node_pending_approval",
                    ok=register_node_body.get("status") == "pending_approval"
                    and bool(node_runtime_credential),
                    details={
                        "status": register_node_body.get("status"),
                        "node_runtime_credential_returned_once": bool(
                            node_runtime_credential
                        ),
                        "raw_node_runtime_credential_redacted": True,
                    },
                )

                approve_body = _require_response(
                    report,
                    stage_name="agent_node_approve",
                    response=client.post(
                        f"/api/v1/maas/{mesh_id}/nodes/{node_id}/approve",
                        headers={"X-API-Key": api_key},
                    ),
                    expected_status=200,
                    details={"owner_rbac_permission_expected": "node:approve"},
                )
                _assert_ready_condition(
                    report,
                    name="agent_node_approved",
                    ok=str(approve_body.get("status") or "").lower()
                    in {"approved", "success"},
                    details={"status": approve_body.get("status")},
                )

                heartbeat_body = _require_response(
                    report,
                    stage_name="agent_heartbeat",
                    response=_post_json(
                        client,
                        f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heartbeat",
                        json_body={
                            "status": "healthy",
                            "latency_ms": 1.0,
                            "traffic_mbps": 0.0,
                            "active_connections": 0,
                            "dataplane_probe_target": dataplane_probe_target,
                        },
                        api_key=node_runtime_credential,
                    ),
                    expected_status=200,
                    details={"dataplane_probe_target_expected_redacted": True},
                )
                _assert_ready_condition(
                    report,
                    name="heartbeat_dataplane_probe_target_redacted",
                    ok=heartbeat_body.get("dataplane_probe_target_registered") is True
                    and heartbeat_body.get("raw_dataplane_probe_target_redacted")
                    is True
                    and dataplane_probe_target not in json.dumps(heartbeat_body),
                    details={
                        "dataplane_probe_target_registered": heartbeat_body.get(
                            "dataplane_probe_target_registered"
                        ),
                        "raw_target_redacted": heartbeat_body.get(
                            "raw_dataplane_probe_target_redacted"
                        ),
                    },
                )

                heal_body = _require_response(
                    report,
                    stage_name="node_heal",
                    response=client.post(
                        f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heal",
                        headers={"X-API-Key": api_key},
                    ),
                    expected_status=200,
                    details={"bounded_revalidation_expected": True},
                )
                revalidation = heal_body.get("post_action_dataplane_revalidation")
                if not isinstance(revalidation, dict):
                    revalidation = {}
                report["evidence_gates"]["node_heal"] = {
                    "healing_claim": heal_body.get("healing_claim"),
                    "dataplane_confirmed": heal_body.get("dataplane_confirmed")
                    is True,
                    "post_action_dataplane_revalidated": heal_body.get(
                        "post_action_dataplane_revalidated"
                    )
                    is True,
                    "restored_dataplane_claim_allowed": heal_body.get(
                        "restored_dataplane_claim_allowed"
                    )
                    is True,
                    "traffic_delivery_claim_allowed": revalidation.get(
                        "traffic_delivery_claim_allowed"
                    )
                    is True,
                    "customer_traffic_claim_allowed": revalidation.get(
                        "customer_traffic_claim_allowed"
                    )
                    is True,
                    "production_readiness_claim_allowed": revalidation.get(
                        "production_readiness_claim_allowed"
                    )
                    is True,
                }
                _assert_ready_condition(
                    report,
                    name="heal_bounded_dataplane_revalidated",
                    ok=heal_body.get("dataplane_confirmed") is True
                    and heal_body.get("post_action_dataplane_revalidated") is True
                    and heal_body.get("restored_dataplane_claim_allowed") is True
                    and revalidation.get("traffic_delivery_claim_allowed") is False
                    and revalidation.get("customer_traffic_claim_allowed") is False
                    and revalidation.get("production_readiness_claim_allowed") is False,
                    details=report["evidence_gates"]["node_heal"],
                )

                trace_summary = event_trace_evidence_summary(
                    {
                        "operation": "maas_autonomous_mesh_runtime_smoke",
                        "service_name": "maas-runtime-smoke",
                        "layer": "api_control_plane_runtime_smoke",
                        "dataplane_confirmed": heal_body.get("dataplane_confirmed"),
                        "post_action_dataplane_revalidation": revalidation,
                        "claim_boundary": CLAIM_BOUNDARY,
                        "payloads_redacted": True,
                    }
                )
                profile = trace_summary.get("cross_plane_evidence_profile", {})
                report["evidence_gates"]["service_trace"] = {
                    "available": trace_summary.get("available") is True,
                    "primary_status": profile.get("primary_status"),
                    "dataplane_confirmed": profile.get("dataplane_confirmed")
                    is True,
                    "dataplane_claim_gate_required": profile.get(
                        "dataplane_claim_gate_required"
                    )
                    is True,
                    "dataplane_claim_gate_allowed": profile.get(
                        "dataplane_claim_gate_allowed"
                    )
                    is True,
                    "production_ready_candidate": profile.get(
                        "production_ready_candidate"
                    )
                    is True,
                    "claim_boundary_present": profile.get("claim_boundary_present")
                    is True,
                    "dataplane_claim_blockers": list(
                        profile.get("dataplane_claim_blockers") or []
                    ),
                }
                _assert_ready_condition(
                    report,
                    name="service_trace_dataplane_gate_classified",
                    ok=profile.get("dataplane_confirmed") is True
                    and profile.get("dataplane_claim_gate_required") is True
                    and profile.get("dataplane_claim_gate_allowed") is True
                    and profile.get("production_ready_candidate") is False,
                    details=report["evidence_gates"]["service_trace"],
                )

                db = testing_session()
                try:
                    node = (
                        db.query(MeshNode)
                        .filter(MeshNode.mesh_id == mesh_id, MeshNode.id == node_id)
                        .first()
                    )
                    node_status = getattr(node, "status", None)
                    node_probe_target = getattr(node, "ip_address", None)
                finally:
                    db.close()
                _assert_ready_condition(
                    report,
                    name="node_state_persisted_in_temp_db",
                    ok=node_status == "approved"
                    and node_probe_target == dataplane_probe_target,
                    details={
                        "node_status": node_status,
                        "dataplane_probe_target_hash": _sha256_text(
                            node_probe_target or ""
                        )
                        if node_probe_target
                        else None,
                        "raw_target_redacted": True,
                    },
                )

        report["ready"] = True
        report["decision"] = READY_DECISION
        return finalize(report)
    except SmokeFailure as exc:
        return finalize(exc.report)
    except Exception as exc:  # pragma: no cover - defensive CLI reporting
        report["decision"] = BLOCKED_DECISION
        report["ready"] = False
        report["failure"] = {
            "stage": "unexpected_exception",
            "exception_type": exc.__class__.__name__,
            "message": str(exc)[:500],
        }
        return finalize(report)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event-project-root",
        default="",
        help=(
            "Directory for local EventBus files. Defaults to a temporary directory."
        ),
    )
    parser.add_argument(
        "--db-path",
        default="",
        help="Temporary SQLite DB path. Defaults under --event-project-root.",
    )
    parser.add_argument("--dataplane-probe-target", default="127.0.0.1")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.event_project_root:
        report = run_verification(
            event_project_root=args.event_project_root,
            db_path=args.db_path or None,
            dataplane_probe_target=args.dataplane_probe_target,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="maas-runtime-smoke-") as tmpdir:
            report = run_verification(
                event_project_root=tmpdir,
                db_path=args.db_path or None,
                dataplane_probe_target=args.dataplane_probe_target,
            )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
