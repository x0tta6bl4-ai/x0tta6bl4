"""Unit tests for MaaS supply-chain EventBus evidence."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import src.api.maas_supply_chain as supply_mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus, source_agent: str):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=10,
        )
    ]


class _Query:
    def __init__(self, *, all_results=None, first_result=None):
        self._all_results = list(all_results or [])
        self._first_result = first_result

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._all_results)

    def first(self):
        return self._first_result


class _SupplyChainDb:
    def __init__(self, *, sboms=None, attestation_records=None, node=None):
        self.sboms = list(sboms or [])
        self.attestation_records = list(attestation_records or [])
        self.node = node
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, model):
        if model is supply_mod.SBOMEntry:
            return _Query(
                all_results=self.sboms,
                first_result=self.sboms[0] if self.sboms else None,
            )
        if model is supply_mod.NodeBinaryAttestation:
            return _Query(
                all_results=self.attestation_records,
                first_result=(
                    self.attestation_records[0] if self.attestation_records else None
                ),
            )
        if model is supply_mod.MeshNode:
            return _Query(first_result=self.node)
        return _Query()

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _row):
        return None


def _sbom_row():
    return SimpleNamespace(
        id="supply-sbom-id-secret",
        version="supply-version-secret",
        format="CycloneDX-JSON",
        checksum_sha256="supply-checksum-secret",
        components_json=json.dumps(
            [{"name": "supply-component-name-secret", "version": "1.0"}]
        ),
        attestation_json=json.dumps(
            {
                "type": "Sigstore-Bundle",
                "signer": "supply-signer-secret@example.test",
                "bundle_url": "https://supply-bundle-secret.example/bundle",
            }
        ),
        created_at=datetime(2026, 5, 30, 12, 0, 0),
    )


def _user():
    return SimpleNamespace(
        id="supply-user-id-secret",
        email="supply-user-secret@example.test",
        role="admin",
    )


def test_sbom_read_and_list_publish_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    row = _sbom_row()
    db = _SupplyChainDb(sboms=[row])

    one = asyncio.run(
        supply_mod.get_sbom(row.version, db=db, request=request)
    )
    many = asyncio.run(supply_mod.list_sboms(db=db, request=request))

    assert one["version"] == row.version
    assert many[0]["version"] == row.version
    read_payloads = _payloads(bus, "maas-supply-chain-sbom-read")
    list_payloads = _payloads(bus, "maas-supply-chain-sbom-list-read")
    assert len(read_payloads) == 1
    assert len(list_payloads) == 1
    read_payload = read_payloads[0]
    assert read_payload["operation"] == "maas_supply_chain_sbom_read"
    assert read_payload["service_name"] == "maas-supply-chain-sbom-read"
    assert read_payload["layer"] == "api_supply_chain_sbom_observed_state"
    assert read_payload["version_hash"] == supply_mod._redacted_sha256_prefix(row.version)
    assert read_payload["sbom_id_hash"] == supply_mod._redacted_sha256_prefix(row.id)
    assert read_payload["component_count"] == 1
    assert read_payload["attestation_present"] is True
    assert read_payload["read_only"] is True
    assert list_payloads[0]["sbom_count"] == 1
    assert list_payloads[0]["component_count_total"] == 1

    serialized = json.dumps(read_payloads + list_payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        row.id,
        row.version,
        row.checksum_sha256,
        "supply-component-name-secret",
        "supply-signer-secret@example.test",
        "https://supply-bundle-secret.example/bundle",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_artifact_register_and_binary_verify_publish_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = _user()
    version = "supply-register-version-secret"
    checksum = "supply-register-checksum-secret"
    component_name = "supply-register-component-secret"
    supply_mod._sbom_registry.pop(version, None)
    try:
        result = asyncio.run(
            supply_mod.register_artifact(
                supply_mod.SBOMRegisterRequest(
                    version=version,
                    checksum_sha256=checksum,
                    components=[
                        supply_mod.ComponentEntry(name=component_name, version="1.0")
                    ],
                    attestation=supply_mod.AttestationMeta(
                        signer="supply-register-signer-secret@example.test",
                        signed_at="2026-05-30T12:00:00Z",
                        bundle_url="https://supply-register-bundle-secret.example",
                    ),
                ),
                current_user=user,
                db=SimpleNamespace(),
                request=request,
            )
        )

        assert result["version"] == version
        register_payloads = _payloads(bus, "maas-supply-chain-artifact-register")
        assert len(register_payloads) == 1
        register_payload = register_payloads[0]
        assert register_payload["operation"] == "maas_supply_chain_artifact_register"
        assert register_payload["service_name"] == "maas-supply-chain-artifact-register"
        assert register_payload["control_action"] is True
        assert register_payload["version_hash"] == supply_mod._redacted_sha256_prefix(
            version
        )
        assert register_payload["checksum_hash"] == supply_mod._redacted_sha256_prefix(
            checksum
        )
        assert register_payload["legacy_registry_used"] is True

        sbom = _sbom_row()
        node_id = "supply-verify-node-secret"
        mesh_id = "supply-verify-mesh-secret"
        db = _SupplyChainDb(sboms=[sbom], attestation_records=[], node=None)
        verify = asyncio.run(
            supply_mod.verify_binary(
                supply_mod.BinaryVerifyRequest(
                    node_id=node_id,
                    mesh_id=mesh_id,
                    agent_version=sbom.version,
                    checksum_sha256=sbom.checksum_sha256,
                ),
                db=db,
                request=request,
            )
        )

        assert verify["status"] == "verified"
        verify_payloads = _payloads(bus, "maas-supply-chain-binary-verify")
        assert len(verify_payloads) == 1
        verify_payload = verify_payloads[0]
        assert verify_payload["operation"] == "maas_supply_chain_binary_verify"
        assert verify_payload["service_name"] == "maas-supply-chain-binary-verify"
        assert verify_payload["node_id_hash"] == supply_mod._redacted_sha256_prefix(
            node_id
        )
        assert verify_payload["mesh_id_hash"] == supply_mod._redacted_sha256_prefix(
            mesh_id
        )
        assert verify_payload["integrity"] == "valid"
        assert verify_payload["control_action"] is True

        serialized = json.dumps(register_payloads + verify_payloads, sort_keys=True)
        raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
            encoding="utf-8"
        )
        for raw_value in (
            user.id,
            user.email,
            version,
            checksum,
            component_name,
            "supply-register-signer-secret@example.test",
            "https://supply-register-bundle-secret.example",
            node_id,
            mesh_id,
            sbom.id,
            sbom.version,
            sbom.checksum_sha256,
        ):
            assert raw_value not in serialized
            assert raw_value not in raw_log
    finally:
        supply_mod._sbom_registry.pop(version, None)


def test_attestation_reads_publish_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = _user()
    node_id = "supply-attestation-node-secret"
    mesh_id = "supply-attestation-mesh-secret"
    attestation_id = "supply-attestation-id-secret"
    sbom_id = "supply-attestation-sbom-secret"
    record = SimpleNamespace(
        id=attestation_id,
        node_id=node_id,
        mesh_id=mesh_id,
        sbom_id=sbom_id,
        agent_version="supply-attestation-version-secret",
        status="mismatch",
        verified_at=datetime(2026, 5, 30, 12, 0, 0),
    )
    db = _SupplyChainDb(attestation_records=[record])

    node_result = asyncio.run(
        supply_mod.get_node_attestations(
            node_id,
            current_user=user,
            db=db,
            request=request,
        )
    )
    mesh_result = asyncio.run(
        supply_mod.get_mesh_attestation_report(
            mesh_id,
            current_user=user,
            db=db,
            request=request,
        )
    )

    assert node_result["node_id"] == node_id
    assert mesh_result["integrity"] == "compromised"
    node_payloads = _payloads(bus, "maas-supply-chain-node-attestation-read")
    mesh_payloads = _payloads(bus, "maas-supply-chain-mesh-attestation-read")
    assert len(node_payloads) == 1
    assert len(mesh_payloads) == 1
    assert node_payloads[0]["operation"] == "maas_supply_chain_node_attestation_read"
    assert node_payloads[0]["node_id_hash"] == supply_mod._redacted_sha256_prefix(
        node_id
    )
    assert node_payloads[0]["status_counts"]["mismatch"] == 1
    assert mesh_payloads[0]["operation"] == "maas_supply_chain_mesh_attestation_read"
    assert mesh_payloads[0]["mesh_id_hash"] == supply_mod._redacted_sha256_prefix(
        mesh_id
    )
    assert mesh_payloads[0]["compromised_count"] == 1
    assert mesh_payloads[0]["integrity"] == "compromised"

    serialized = json.dumps(node_payloads + mesh_payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        user.id,
        user.email,
        node_id,
        mesh_id,
        attestation_id,
        sbom_id,
        "supply-attestation-version-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log
