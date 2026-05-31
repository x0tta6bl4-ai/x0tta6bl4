"""Unit tests for legacy MaaS lifecycle EventBus evidence."""

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType


class _BillingService:
    def __init__(self, *, fail: bool = False):
        self.fail = fail

    def check_quota(self, *_args, **_kwargs):
        if self.fail:
            raise RuntimeError("quota secret should not leak")
        return True


class _Db:
    def __init__(self, *, fail_commit: bool = False):
        self.fail_commit = fail_commit
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("db secret should not leak")

    def rollback(self):
        self.rollbacks += 1


class _Provisioner:
    def __init__(self, registry: dict, *, mesh_id: str, join_token: str):
        self.registry = registry
        self.mesh_id = mesh_id
        self.join_token = join_token

    async def create(
        self,
        *,
        user,
        name,
        nodes,
        pqc_enabled,
        obfuscation,
        traffic_profile,
        join_token_ttl_sec,
    ):
        instance = SimpleNamespace(
            mesh_id=self.mesh_id,
            name=name,
            owner_id=user.id,
            target_nodes=nodes,
            status="active",
            plan=None,
            pqc_profile=None,
            join_token=self.join_token,
            join_token_ttl_sec=join_token_ttl_sec,
            join_token_expires_at=datetime.utcnow()
            + timedelta(seconds=join_token_ttl_sec),
            pqc_enabled=pqc_enabled,
            obfuscation=obfuscation,
            traffic_profile=traffic_profile,
            created_at=datetime.utcnow(),
            node_instances={
                f"{self.mesh_id}-node-{idx}": {"status": "healthy"}
                for idx in range(nodes)
            },
        )
        self.registry[self.mesh_id] = instance
        return instance


class _ReadProvisioner:
    def __init__(self, instances):
        self.instances = {instance.mesh_id: instance for instance in instances}

    def list_for_owner(self, owner_id):
        return [
            instance
            for instance in self.instances.values()
            if str(instance.owner_id) == str(owner_id)
        ]

    def get(self, mesh_id):
        return self.instances.get(mesh_id)


class _ReadMesh:
    def __init__(self, *, mesh_id: str, owner_id: str, name: str):
        self.mesh_id = mesh_id
        self.owner_id = owner_id
        self.name = name
        self.status = "active"
        self.pqc_enabled = True
        self.obfuscation = "none"
        self.traffic_profile = "voip"
        self.created_at = datetime.utcnow()
        self.node_instances = {
            f"{mesh_id}-secret-node-1": {"status": "healthy"},
            f"{mesh_id}-secret-node-2": {"status": "pending"},
        }

    def get_uptime(self):
        return 42.0

    def get_health_score(self):
        return 0.5

    def get_consciousness_metrics(self):
        return {"awareness": 0.7, "private_signal": "metric-secret-value"}

    def get_mape_k_state(self):
        return {"phase": "analyze", "private_state": "mapek-secret-value"}

    def get_network_metrics(self):
        return {"latency_ms": 12, "private_path": "network-secret-value"}


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _deploy_request(name: str):
    return legacy_mod.MeshDeployRequest(
        name=name,
        nodes=2,
        billing_plan="starter",
        pqc_enabled=True,
        obfuscation="none",
        traffic_profile="none",
        join_token_ttl_sec=3600,
    )


def _payloads(bus: EventBus, source_agent: str = "maas-legacy-lifecycle"):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=10,
        )
    ]


def test_legacy_deploy_success_publishes_redacted_lifecycle_evidence(
    monkeypatch,
    tmp_path,
):
    registry = {}
    mesh_id = "mesh-secret-lifecycle"
    owner_id = "owner-secret-lifecycle"
    join_token = "join-token-secret-lifecycle"
    mesh_name = "secret lifecycle mesh"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    monkeypatch.setattr(legacy_mod, "_mesh_registry", registry)
    monkeypatch.setattr(legacy_mod, "billing_service", _BillingService())
    monkeypatch.setattr(
        legacy_mod,
        "mesh_provisioner",
        _Provisioner(registry, mesh_id=mesh_id, join_token=join_token),
    )

    result = asyncio.run(
        legacy_mod.deploy_mesh(
            _deploy_request(mesh_name),
            current_user=SimpleNamespace(id=owner_id, role="admin", plan="starter"),
            db=_Db(),
            request=request,
        )
    )

    assert result.mesh_id == mesh_id
    assert result.join_config["token"] == join_token
    assert mesh_id in registry

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_mesh_deploy"
    assert payload["service_name"] == "maas-legacy-lifecycle"
    assert payload["source_alias"] == "maas-legacy-lifecycle"
    assert payload["layer"] == "api_legacy_lifecycle_control_action"
    assert payload["stage"] == "deployed"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["node_count"] == 2
    assert payload["registry_mutated"] is True
    assert payload["db_persisted"] is True
    assert payload["join_token_issued"] is True
    assert payload["request_summary"]["mesh_name_present"] is True
    assert payload["request_summary"]["requested_nodes"] == 2
    assert payload["read_only"] is False
    assert payload["control_action"] is True
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, join_token, mesh_name):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_deploy_db_failure_publishes_redacted_rollback_evidence(
    monkeypatch,
    tmp_path,
):
    registry = {}
    mesh_id = "mesh-secret-db-failure"
    owner_id = "owner-secret-db-failure"
    join_token = "join-token-secret-db-failure"
    mesh_name = "secret db failure mesh"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    monkeypatch.setattr(legacy_mod, "_mesh_registry", registry)
    monkeypatch.setattr(legacy_mod, "billing_service", _BillingService())
    monkeypatch.setattr(
        legacy_mod,
        "mesh_provisioner",
        _Provisioner(registry, mesh_id=mesh_id, join_token=join_token),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            legacy_mod.deploy_mesh(
                _deploy_request(mesh_name),
                current_user=SimpleNamespace(
                    id=owner_id,
                    role="admin",
                    plan="starter",
                ),
                db=_Db(fail_commit=True),
                request=request,
            )
        )

    assert exc.value.status_code == 500
    assert mesh_id not in registry

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "db_persist_failed"
    assert payload["status"] == "failed"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["registry_mutated"] is True
    assert payload["db_persisted"] is False
    assert payload["join_token_issued"] is True
    assert payload["reason"] == "db_persist_failed"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        owner_id,
        join_token,
        mesh_name,
        "db secret should not leak",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_list_meshes_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-list-read"
    owner_id = "owner-secret-list-read"
    mesh_name = "secret list read mesh"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _ReadMesh(mesh_id=mesh_id, owner_id=owner_id, name=mesh_name)

    from src.api.maas import registry as modular_registry

    monkeypatch.setattr(
        legacy_mod,
        "mesh_provisioner",
        _ReadProvisioner([instance]),
    )
    monkeypatch.setattr(modular_registry, "get_all_meshes", lambda: {})

    result = asyncio.run(
        legacy_mod.legacy_list_meshes(
            request=request,
            current_user=SimpleNamespace(id=owner_id, role="user"),
        )
    )

    assert result["count"] == 1
    assert result["meshes"][0]["mesh_id"] == mesh_id

    payloads = _payloads(bus, "maas-legacy-lifecycle-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_mesh_list_read"
    assert payload["service_name"] == "maas-legacy-lifecycle-read"
    assert payload["source_alias"] == "maas-legacy-lifecycle-read"
    assert payload["layer"] == "api_legacy_lifecycle_observed_state"
    assert payload["stage"] == "list_read"
    assert payload["status"] == "success"
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["mesh_count"] == 1
    assert payload["node_count"] == 2
    assert payload["healthy_node_count"] == 1
    assert payload["read_only"] is True
    assert payload["observed_state"] is True
    assert payload["control_action"] is False
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, mesh_name, f"{mesh_id}-secret-node-1"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_mesh_status_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-status-read"
    owner_id = "owner-secret-status-read"
    mesh_name = "secret status read mesh"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _ReadMesh(mesh_id=mesh_id, owner_id=owner_id, name=mesh_name)

    monkeypatch.setattr(
        legacy_mod,
        "mesh_provisioner",
        _ReadProvisioner([instance]),
    )

    result = asyncio.run(
        legacy_mod.legacy_mesh_status(
            mesh_id=mesh_id,
            request=request,
            current_user=SimpleNamespace(id=owner_id, role="user"),
        )
    )

    assert result.mesh_id == mesh_id
    assert result.peers[0]["node_id"] == f"{mesh_id}-secret-node-1"

    payloads = _payloads(bus, "maas-legacy-lifecycle-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_mesh_status_read"
    assert payload["stage"] == "status_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["node_count"] == 2
    assert payload["healthy_node_count"] == 1
    assert payload["result_summary"]["peer_count"] == 2
    assert payload["read_only"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, mesh_name, f"{mesh_id}-secret-node-1"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_mesh_metrics_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-metrics-read"
    owner_id = "owner-secret-metrics-read"
    mesh_name = "secret metrics read mesh"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _ReadMesh(mesh_id=mesh_id, owner_id=owner_id, name=mesh_name)

    monkeypatch.setattr(
        legacy_mod,
        "mesh_provisioner",
        _ReadProvisioner([instance]),
    )

    result = asyncio.run(
        legacy_mod.legacy_mesh_metrics(
            mesh_id=mesh_id,
            request=request,
            current_user=SimpleNamespace(id=owner_id, role="user"),
        )
    )

    assert result.mesh_id == mesh_id
    assert result.consciousness["private_signal"] == "metric-secret-value"
    assert (
        result.mesh_metrics_claim_gate[
            "local_mesh_metrics_observation_claim_allowed"
        ]
        is True
    )
    assert (
        result.mesh_metrics_claim_gate["production_readiness_claim_allowed"] is False
    )
    assert result.mesh_metrics_claim_gate["dataplane_delivery_claim_allowed"] is False
    assert result.mesh_metrics_claim_gate["external_dpi_bypass_claim_allowed"] is False
    assert result.mesh_metrics_claim_gate["settlement_finality_claim_allowed"] is False
    assert result.cross_plane_claim_gate["surface"] == "legacy_maas_mesh.metrics"
    assert result.cross_plane_claim_gate["allowed"] is False

    payloads = _payloads(bus, "maas-legacy-lifecycle-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_mesh_metrics_read"
    assert payload["stage"] == "metrics_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["result_summary"]["consciousness_metric_count"] == 2
    assert payload["result_summary"]["mape_k_metric_count"] == 2
    assert payload["result_summary"]["network_metric_count"] == 2
    assert payload["result_summary"]["mesh_metrics_claim_gate_present"] is True
    assert payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert payload["result_summary"]["production_readiness_claim_allowed"] is False
    assert payload["result_summary"]["dataplane_delivery_claim_allowed"] is False
    assert payload["result_summary"]["external_dpi_bypass_claim_allowed"] is False
    assert payload["result_summary"]["has_timestamp"] is True
    assert payload["read_only"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        owner_id,
        mesh_name,
        "metric-secret-value",
        "mapek-secret-value",
        "network-secret-value",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_mesh_status_denial_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    missing_mesh_id = "mesh-secret-status-denied"
    owner_id = "owner-secret-status-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    from src.api.maas import registry as modular_registry

    monkeypatch.setattr(legacy_mod, "mesh_provisioner", _ReadProvisioner([]))
    monkeypatch.setattr(modular_registry, "get_mesh", lambda _mesh_id: None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            legacy_mod.legacy_mesh_status(
                mesh_id=missing_mesh_id,
                request=request,
                current_user=SimpleNamespace(id=owner_id, role="user"),
            )
        )

    assert exc.value.status_code == 404

    payloads = _payloads(bus, "maas-legacy-lifecycle-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_mesh_status_read"
    assert payload["stage"] == "access_denied"
    assert payload["status"] == "denied"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(
        missing_mesh_id
    )
    assert payload["actor_user_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["read_only"] is True
    assert payload["reason"] == "mesh_not_found_or_forbidden"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (missing_mesh_id, owner_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log
