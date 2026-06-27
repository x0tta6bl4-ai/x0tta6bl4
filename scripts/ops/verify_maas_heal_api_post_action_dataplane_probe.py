#!/usr/bin/env python3
"""Verify MaaS API heal path carries bounded post-action dataplane evidence.

This verifier exercises the production-like HTTP caller path:

1. a node heartbeat registers a redacted dataplane probe target;
2. an operator calls the MaaS node heal endpoint;
3. the heal path passes that target into the mesh healing manager;
4. the response surfaces bounded post-action dataplane evidence without
   promoting traffic, customer, external reachability, SLO, or production claims.

It uses a temporary SQLite database and a fake mesh manager that emits the same
redacted EventBus shape as the real manager. It does not perform live customer
traffic, external reachability, DPI, settlement, or production-readiness proof.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SCHEMA = "x0tta6bl4.maas_heal_api_post_action_dataplane_probe.v1"
DECISION_READY = "MAAS_HEAL_API_POST_ACTION_DATAPLANE_PROBE_READY"
DECISION_BLOCKED = "MAAS_HEAL_API_POST_ACTION_DATAPLANE_PROBE_BLOCKED"
DEFAULT_OUTPUT_JSON = Path(
    ".tmp/validation-shards/maas-heal-api-post-action-dataplane-probe-current.json"
)
CLAIM_BOUNDARY = (
    "MaaS API post-action dataplane verifier. It proves the local HTTP "
    "heartbeat->heal caller path can carry a redacted probe target into bounded "
    "post-action dataplane evidence. It does not prove live customer traffic, "
    "external reachability, DPI bypass, settlement finality, production SLOs, "
    "or production readiness."
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _load_project_runtime() -> dict[str, Any]:
    # src.core.app emits startup logs on import; keep --json stdout machine-readable.
    with contextlib.redirect_stdout(sys.stderr):
        from src.api.maas.nodes import healing as healing_mod
        from src.api.maas.nodes import hash_node_runtime_credential
        from src.api.maas_security import ApiKeyManager
        from src.coordination.events import EventBus, EventType
        from src.core.app import app
        from src.database import Base, MeshInstance, MeshNode, User, get_db

    return {
        "ApiKeyManager": ApiKeyManager,
        "Base": Base,
        "EventBus": EventBus,
        "EventType": EventType,
        "MeshInstance": MeshInstance,
        "MeshNode": MeshNode,
        "User": User,
        "app": app,
        "get_db": get_db,
        "hash_node_runtime_credential": hash_node_runtime_credential,
        "healing_mod": healing_mod,
    }


def _seed_admin_mesh_node(
    testing_session: Any,
    *,
    runtime: dict[str, Any],
) -> dict[str, str]:
    ApiKeyManager = runtime["ApiKeyManager"]
    MeshInstance = runtime["MeshInstance"]
    MeshNode = runtime["MeshNode"]
    User = runtime["User"]
    hash_node_runtime_credential = runtime["hash_node_runtime_credential"]
    api_key = f"maas_api_probe_{uuid.uuid4().hex}"
    user_id = f"usr-{uuid.uuid4().hex[:12]}"
    mesh_id = f"mesh-{uuid.uuid4().hex[:12]}"
    node_id = f"node-{uuid.uuid4().hex[:12]}"
    node_runtime_credential = f"x0tn_probe_{uuid.uuid4().hex}"

    db = testing_session()
    try:
        db.add(
            User(
                id=user_id,
                email=f"{user_id}@test.local",
                password_hash="test-hash",
                api_key=None,
                api_key_hash=ApiKeyManager.hash_key(api_key),
                role="admin",
                plan="enterprise",
            )
        )
        db.add(
            MeshInstance(
                id=mesh_id,
                name="API Post Action Dataplane Probe",
                owner_id=user_id,
                plan="enterprise",
                status="active",
                join_token=f"join-{uuid.uuid4().hex}",
            )
        )
        db.add(
            MeshNode(
                id=node_id,
                mesh_id=mesh_id,
                device_class="edge",
                status="approved",
                runtime_credential_hash=hash_node_runtime_credential(
                    node_runtime_credential
                ),
                runtime_credential_expires_at=datetime.now(timezone.utc).replace(
                    tzinfo=None
                )
                + timedelta(hours=1),
            )
        )
        db.commit()
    finally:
        db.close()

    return {
        "api_key": api_key,
        "mesh_id": mesh_id,
        "node_id": node_id,
        "node_runtime_credential": node_runtime_credential,
    }


def _install_fake_healing_manager(
    *,
    healing_mod: Any,
    EventType: Any,
    event_bus: Any,
    captured: dict[str, Any],
) -> dict[str, Any]:
    original = {
        "MESH_HEALING_AVAILABLE": healing_mod.MESH_HEALING_AVAILABLE,
        "VerificationMode": healing_mod.VerificationMode,
        "MeshNetworkManager": healing_mod.MeshNetworkManager,
        "get_event_bus": healing_mod.get_event_bus,
    }

    class FakeVerificationMode:
        FULL = "full"

    class FakeMeshNetworkManager:
        def __init__(self, **kwargs: Any) -> None:
            captured["manager_kwargs"] = {
                "event_bus_attached": kwargs.get("event_bus") is event_bus,
                "event_project_root_present": bool(kwargs.get("event_project_root")),
                "node_id_present": bool(kwargs.get("node_id")),
            }
            self.event_bus = kwargs["event_bus"]

        async def trigger_aggressive_healing(
            self,
            *,
            auto_restore_nodes: bool,
            verification_mode: str,
            post_action_dataplane_probe_target: str | None = None,
        ) -> int:
            captured["healing_call"] = {
                "auto_restore_nodes": auto_restore_nodes is True,
                "verification_mode_full": verification_mode == "full",
                "probe_target_hash": sha256_text(
                    str(post_action_dataplane_probe_target or "")
                ),
                "probe_target_present": bool(post_action_dataplane_probe_target),
            }
            evidence = {
                "source_agents": ["bounded-dataplane-probe"],
                "event_ids": ["evt-api-post-action-probe"],
                "event_ids_count": 1,
                "events_total": 1,
                "redacted": True,
            }
            claim_boundary = "bounded API caller dataplane probe evidence only"
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
                "local_action_applied": True,
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
    healing_mod.get_event_bus = lambda _project_root: event_bus
    return original


def _restore_fake_healing_manager(original: dict[str, Any]) -> None:
    healing_mod = original.pop("healing_mod")
    for name, value in original.items():
        setattr(healing_mod, name, value)


def _validate_report(report: dict[str, Any], *, raw_target: str) -> list[str]:
    failures: list[str] = []
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    if summary.get("heartbeat_registered_probe_target") is not True:
        failures.append("heartbeat_probe_target_not_registered")
    if summary.get("heartbeat_raw_target_redacted") is not True:
        failures.append("heartbeat_target_not_redacted")
    if summary.get("heal_status_ok") is not True:
        failures.append("heal_api_status_not_ok")
    if summary.get("manager_received_probe_target") is not True:
        failures.append("manager_probe_target_not_received")
    if summary.get("dataplane_confirmed") is not True:
        failures.append("dataplane_not_confirmed")
    if summary.get("post_action_dataplane_revalidated") is not True:
        failures.append("post_action_dataplane_not_revalidated")
    if summary.get("restored_dataplane_claim_allowed") is not True:
        failures.append("restored_dataplane_not_allowed")
    for field in (
        "traffic_delivery_claim_allowed",
        "customer_traffic_claim_allowed",
        "external_reachability_claim_allowed",
        "production_slo_claim_allowed",
        "production_readiness_claim_allowed",
    ):
        if summary.get(field) is not False:
            failures.append(f"{field}_overclaimed")
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True)
    if raw_target and raw_target in rendered:
        failures.append("raw_target_leaked")
    return failures


def build_report(
    root: Path,
    *,
    target: str = "127.0.0.1",
) -> dict[str, Any]:
    root = root.resolve()
    runtime = _load_project_runtime()
    app = runtime["app"]
    Base = runtime["Base"]
    EventBus = runtime["EventBus"]
    EventType = runtime["EventType"]
    get_db = runtime["get_db"]
    healing_mod = runtime["healing_mod"]
    captured: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="x0t-maas-api-probe-") as tmpdir:
        tmp_root = Path(tmpdir)
        db_path = tmp_root / "maas-api-probe.db"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        testing_session = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
        event_bus = EventBus(project_root=str(tmp_root / "events"))

        def override_get_db():
            db = testing_session()
            try:
                yield db
            finally:
                db.close()

        previous_override = app.dependency_overrides.get(get_db)
        original_healing = _install_fake_healing_manager(
            healing_mod=healing_mod,
            EventType=EventType,
            event_bus=event_bus,
            captured=captured,
        )
        original_healing["healing_mod"] = healing_mod
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db
        try:
            seeded = _seed_admin_mesh_node(testing_session, runtime=runtime)
            with TestClient(app) as client:
                heartbeat = client.post(
                    f"/api/v1/maas/{seeded['mesh_id']}/nodes/{seeded['node_id']}/heartbeat",
                    json={
                        "status": "healthy",
                        "latency_ms": 1.0,
                        "dataplane_probe_target": target,
                    },
                    headers={"X-API-Key": seeded["node_runtime_credential"]},
                )
                heartbeat_body = (
                    heartbeat.json()
                    if heartbeat.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
                heal = client.post(
                    f"/api/v1/maas/{seeded['mesh_id']}/nodes/{seeded['node_id']}/heal",
                    headers={"X-API-Key": seeded["api_key"]},
                )
                heal_body = (
                    heal.json()
                    if heal.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                    else {}
                )
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_override
            _restore_fake_healing_manager(original_healing)
            Base.metadata.drop_all(bind=engine)

    revalidation = (
        heal_body.get("post_action_dataplane_revalidation")
        if isinstance(heal_body, dict)
        else {}
    )
    if not isinstance(revalidation, dict):
        revalidation = {}
    claim_gate = (
        revalidation.get("claim_gate")
        if isinstance(revalidation.get("claim_gate"), dict)
        else {}
    )
    target_hash = sha256_text(target)
    summary = {
        "api_path_exercised": True,
        "heartbeat_status_ok": heartbeat.status_code == 200,
        "heartbeat_registered_probe_target": (
            heartbeat_body.get("dataplane_probe_target_registered") is True
        ),
        "heartbeat_raw_target_redacted": (
            heartbeat_body.get("raw_dataplane_probe_target_redacted") is True
        ),
        "heal_status_ok": heal.status_code == 200,
        "manager_received_probe_target": (
            captured.get("healing_call", {}).get("probe_target_hash")
            == target_hash
        ),
        "manager_event_bus_attached": (
            captured.get("manager_kwargs", {}).get("event_bus_attached") is True
        ),
        "dataplane_confirmed": heal_body.get("dataplane_confirmed") is True,
        "post_action_dataplane_revalidated": (
            heal_body.get("post_action_dataplane_revalidated") is True
        ),
        "restored_dataplane_claim_allowed": (
            heal_body.get("restored_dataplane_claim_allowed") is True
        ),
        "claim_gate_restored_dataplane_allowed": (
            claim_gate.get("restored_dataplane_claim_allowed") is True
        ),
        "traffic_delivery_claim_allowed": revalidation.get(
            "traffic_delivery_claim_allowed"
        )
        is True,
        "customer_traffic_claim_allowed": revalidation.get(
            "customer_traffic_claim_allowed"
        )
        is True,
        "external_reachability_claim_allowed": revalidation.get(
            "external_reachability_claim_allowed"
        )
        is True,
        "production_slo_claim_allowed": revalidation.get(
            "production_slo_claim_allowed"
        )
        is True,
        "production_readiness_claim_allowed": revalidation.get(
            "production_readiness_claim_allowed"
        )
        is True,
        "raw_target_redacted": True,
    }
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "decision": DECISION_BLOCKED,
        "ok": False,
        "target": {
            "sha256": target_hash,
            "raw_target_redacted": True,
        },
        "summary": summary,
        "evidence": {
            "control_plane_operations": list(
                heal_body.get("control_plane_evidence", {}).get("operations", [])
                if isinstance(heal_body.get("control_plane_evidence"), dict)
                else []
            ),
            "post_action_reason": str(revalidation.get("reason") or ""),
            "post_action_status": str(revalidation.get("status") or ""),
            "claim_gate_decision": str(claim_gate.get("decision") or ""),
            "event_root_retained": False,
            "redacted": True,
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "failures": [],
    }
    failures = _validate_report(report, raw_target=target)
    ready = not failures
    report["failures"] = failures
    report["decision"] = DECISION_READY if ready else DECISION_BLOCKED
    report["ok"] = ready
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--target", default="127.0.0.1")
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.root, target=args.target)
    if args.output_json:
        output = args.output_json if args.output_json.is_absolute() else args.root / args.output_json
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"decision={report['decision']}")
        print(f"ok={report['ok']}")
        for failure in report["failures"]:
            print(f"- {failure}")
    return 0 if report["ok"] or not args.require_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
