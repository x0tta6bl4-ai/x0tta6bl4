"""Unit tests for MaaS compatibility auth/deploy EventBus evidence."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

import src.api.maas_compat as compat_mod
from src.api.maas.models import MeshDeployRequest, MeshDeployResponse
from src.api.maas_auth_models import UserRegisterRequest
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


def test_compat_register_success_publishes_redacted_alias_evidence(
    monkeypatch,
    tmp_path,
):
    email = "compat-register-secret@example.test"
    password = "super-private-password"
    full_name = "Private Register User"
    company = "Private Company"
    access_token = "x0t-register-secret-token"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    register_request = UserRegisterRequest(
        email=email,
        password=password,
        full_name=full_name,
        company=company,
    )

    async def _register(req, db):
        return {
            "access_token": access_token,
            "token_type": "api_key",
            "expires_in": 31536000,
        }

    monkeypatch.setattr(compat_mod, "register_v1", _register)

    result = asyncio.run(
        compat_mod.register_v3_alias(
            register_request,
            request,
            db=SimpleNamespace(),
        )
    )

    assert result["access_token"] == access_token
    payloads = _payloads(bus, "maas-compat-auth-register")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_auth_register"
    assert payload["service_name"] == "maas-compat-auth-register"
    assert payload["source_alias"] == "maas-compat-auth-register"
    assert payload["layer"] == "api_compat_auth_registration_intent"
    assert payload["stage"] == "auth_register_delegated"
    assert payload["status"] == "success"
    assert payload["delegated_to_auth"] is True
    assert payload["http_status_code"] == 200
    assert payload["request_summary"] == {
        "email_present": True,
        "password_present": True,
        "full_name_present": True,
        "company_present": True,
    }
    assert payload["result_summary"] == {
        "payload_type": "dict",
        "payload_field_count": 3,
        "access_token_present": True,
        "token_type": "api_key",
        "expires_in_present": True,
    }
    assert payload["control_action"] is True
    assert payload["raw_identifiers_redacted"] is True
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, password, full_name, company, access_token):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_register_http_failure_publishes_redacted_alias_evidence(
    monkeypatch,
    tmp_path,
):
    email = "compat-register-failed-secret@example.test"
    password = "super-private-password"
    private_detail = "private duplicate email detail"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    register_request = UserRegisterRequest(email=email, password=password)

    async def _register(req, db):
        raise HTTPException(status_code=409, detail=private_detail)

    monkeypatch.setattr(compat_mod, "register_v1", _register)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.register_v3_alias(
                register_request,
                request,
                db=SimpleNamespace(),
            )
        )

    assert exc.value.status_code == 409
    payloads = _payloads(bus, "maas-compat-auth-register")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "auth_register_failed"
    assert payload["status"] == "failed"
    assert payload["delegated_to_auth"] is True
    assert payload["http_status_code"] == 409
    assert payload["reason"] == "http_409"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, password, private_detail):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_deploy_success_publishes_redacted_alias_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_name = "private-compat-deploy-mesh"
    mesh_id = "mesh-private-compat-deploy"
    owner_id = "owner-private-compat-deploy"
    join_token = "join-token-private-compat-deploy"
    dashboard_url = f"/api/v1/maas/mesh/{mesh_id}/status"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()
    deploy_request = MeshDeployRequest(
        name=mesh_name,
        nodes=3,
        billing_plan="pro",
        pqc_enabled=True,
        obfuscation="xor",
        traffic_profile="gaming",
        join_token_ttl_sec=7200,
    )

    async def _deploy_mesh(*, request, user, db):
        return MeshDeployResponse(
            mesh_id=mesh_id,
            join_config={"enrollment_token": join_token, "ttl_sec": 7200},
            dashboard_url=dashboard_url,
            status="active",
            pqc_identity={"enabled": True, "profile": "edge"},
            pqc_enabled=True,
            created_at="2026-05-30T00:00:00",
            plan="pro",
            join_token_expires_at="2026-05-30T02:00:00",
            mesh_deploy_claim_gate={"schema": "unit.deploy.v1"},
            mesh_provisioner_claim_gate={"schema": "unit.provisioner.v1"},
            provisioner_cross_plane_claim_gate={
                "schema": "unit.provisioner_cross_plane.v1"
            },
            cross_plane_claim_gate={"schema": "unit.cross_plane.v1"},
        )

    monkeypatch.setattr(compat_mod.modular_mesh, "deploy_mesh", _deploy_mesh)

    result = asyncio.run(
        compat_mod.deploy_mesh_alias(
            deploy_request,
            request,
            http_response=http_response,
            current_user=SimpleNamespace(id=owner_id, role="user", plan="pro"),
            db=SimpleNamespace(),
        )
    )

    assert result.mesh_id == mesh_id
    assert result.join_config["enrollment_token"] == join_token
    assert (
        http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
        == "x0tta6bl4.maas_compat_lifecycle_control_claim_boundary_headers.v1"
    )
    assert http_response.headers["X-X0TTA6BL4-Claim-Surface"] == (
        "maas_compat.lifecycle_control.deploy"
    )
    assert http_response.headers[
        "X-X0TTA6BL4-Delegated-Modular-Lifecycle-Claim-Allowed"
    ] == "true"
    assert http_response.headers[
        "X-X0TTA6BL4-External-Node-Deployment-Claim-Allowed"
    ] == "false"
    assert http_response.headers[
        "X-X0TTA6BL4-Production-Readiness-Claim-Allowed"
    ] == "false"
    payloads = _payloads(bus, "maas-compat-deploy")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_mesh_deploy"
    assert payload["service_name"] == "maas-compat-deploy"
    assert payload["source_alias"] == "maas-compat-deploy"
    assert payload["layer"] == "api_compat_lifecycle_control_action"
    assert payload["stage"] == "deploy_delegated"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["delegated_to_modular"] is True
    assert payload["registry_mutated"] is True
    assert payload["http_status_code"] == 201
    assert payload["request_summary"]["name_present"] is True
    assert payload["request_summary"]["name_length"] == len(mesh_name)
    assert payload["request_summary"]["nodes"] == 3
    assert payload["request_summary"]["billing_plan"] == "pro"
    assert payload["request_summary"]["join_token_ttl_sec"] == 7200
    assert payload["result_summary"] == {
        "status": "active",
        "plan": "pro",
        "join_config_field_count": 2,
        "join_token_present": True,
        "dashboard_url_present": True,
        "pqc_identity_present": True,
        "pqc_identity_field_count": 2,
        "created_at_present": True,
        "join_token_expires_at_present": True,
        "mesh_deploy_claim_gate_present": True,
        "mesh_provisioner_claim_gate_present": True,
        "provisioner_cross_plane_claim_gate_present": True,
        "cross_plane_claim_gate_present": True,
        "compat_lifecycle_control_claim_gate_present": True,
        "compat_lifecycle_control_claim_boundary_headers_present": True,
        "claim_surface": "maas_compat.lifecycle_control.deploy",
    }
    assert payload["raw_identifiers_redacted"] is True
    assert payload["raw_join_token_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_name, mesh_id, owner_id, join_token, dashboard_url):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_deploy_http_failure_publishes_redacted_alias_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_name = "private-compat-deploy-failed"
    owner_id = "owner-private-compat-deploy-failed"
    private_detail = "private deploy failure detail"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    deploy_request = MeshDeployRequest(name=mesh_name, nodes=2)

    async def _deploy_mesh(*, request, user, db):
        raise HTTPException(status_code=400, detail=private_detail)

    monkeypatch.setattr(compat_mod.modular_mesh, "deploy_mesh", _deploy_mesh)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.deploy_mesh_alias(
                deploy_request,
                request,
                current_user=SimpleNamespace(id=owner_id, role="user", plan="starter"),
                db=SimpleNamespace(),
            )
        )

    assert exc.value.status_code == 400
    payloads = _payloads(bus, "maas-compat-deploy")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "deploy_failed"
    assert payload["status"] == "failed"
    assert payload["delegated_to_modular"] is True
    assert payload["registry_mutated"] is False
    assert payload["http_status_code"] == 400
    assert payload["reason"] == "http_400"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_name, owner_id, private_detail):
        assert raw_value not in serialized
        assert raw_value not in raw_log
