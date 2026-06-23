from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import maas_provisioning as mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


class _DB:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_generate_setup_emits_redacted_provisioning_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    db = _DB()
    user = SimpleNamespace(
        id="user-private",
        email="owner@example.com",
        role="operator",
    )
    request = mod.ProvisionRequest(
        mesh_id="mesh-private",
        device_name="edge-node-private",
        device_class="edge",
        os_type="linux",
    )

    response = asyncio.run(
        mod.generate_provisioning_setup(
            request,
            current_user=user,
            db=db,
            request=_request(bus),
        )
    )
    decoded_config = json.loads(base64.b64decode(response.config_json).decode())
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod._PROVISIONING_SETUP_SOURCE_AGENT,
        limit=10,
    )
    payload = events[-1].data
    payload_text = str(payload)

    assert db.commits == 1
    assert db.added[-1].id == response.node_id
    assert decoded_config["join_token"] == response.join_token
    assert payload["status"] == "created"
    assert payload["control_action"] is True
    assert payload["db_write_succeeded"] is True
    assert payload["provisioning_setup_claim_gate"][
        "local_pending_node_db_write_claim_allowed"
    ] is True
    assert payload["provisioning_setup_claim_gate"][
        "install_command_executed_claim_allowed"
    ] is False
    assert payload["provisioning_setup_claim_gate"][
        "node_dataplane_join_claim_allowed"
    ] is False
    assert payload["join_token_present"] is True
    assert payload["install_command_length"] == len(response.install_command)
    assert response.provisioning_setup_claim_gate[
        "local_setup_package_generation_claim_allowed"
    ] is True
    assert response.provisioning_setup_claim_gate[
        "node_reachability_claim_allowed"
    ] is False
    assert response.provisioning_setup_claim_gate[
        "production_readiness_claim_allowed"
    ] is False
    assert response.cross_plane_claim_gate["surface"] == "maas_provisioning.generate_setup"
    assert response.cross_plane_claim_gate["allowed"] is False
    assert payload["raw_mesh_id_redacted"] is True
    assert payload["raw_device_name_redacted"] is True
    assert payload["raw_join_token_redacted"] is True
    assert payload["raw_install_command_redacted"] is True
    assert payload["raw_config_redacted"] is True
    assert "mesh-private" not in payload_text
    assert "edge-node-private" not in payload_text
    assert response.node_id not in payload_text
    assert response.join_token not in payload_text
    assert response.install_command not in payload_text
    assert response.config_json not in payload_text
    assert "owner@example.com" not in payload_text
    assert "user-private" not in payload_text


def test_provisioning_readiness_marks_missing_database_dependency():
    request = SimpleNamespace(state=SimpleNamespace())

    payload = asyncio.run(mod.provisioning_readiness(request=request, db=object()))

    assert payload["readiness_status"] == "degraded"
    assert payload["provisioning_runtime_ready"] is False
    assert payload["db_write_ready"] is False
    assert payload["event_bus_ready"] is True
    assert payload["auth_dependency_ready"] is True
    assert payload["cross_plane_claim_gate"]["allowed"] is False
    assert "dataplane_delivery" in payload["cross_plane_claim_gate"]["requested_claim_ids"]
    assert payload["degraded_dependencies"] == ["database"]
    assert request.state.degraded_dependencies == {"database"}


def test_fastapi_router_injects_request_event_bus_for_generate_setup(tmp_path):
    app = FastAPI()
    bus = EventBus(str(tmp_path))
    db = _DB()

    @app.middleware("http")
    async def _inject_event_bus(request, call_next):
        request.state.event_bus = bus
        return await call_next(request)

    def _db_override():
        yield db

    app.dependency_overrides[mod.get_current_user_from_maas] = lambda: SimpleNamespace(
        id="user-private",
        email="owner@example.com",
        role="operator",
    )
    app.dependency_overrides[mod.get_db] = _db_override
    app.include_router(mod.router)

    client = TestClient(app)
    response = client.post(
        "/api/v1/maas/provisioning/generate-setup",
        json={
            "mesh_id": "mesh-private",
            "device_name": "edge-node-private",
            "device_class": "edge",
            "os_type": "linux",
        },
    )
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod._PROVISIONING_SETUP_SOURCE_AGENT,
        limit=10,
    )

    assert response.status_code == 200, response.text
    assert (
        response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
        == "x0tta6bl4.maas_provisioning_setup_claim_gate.v1"
    )
    assert (
        response.headers["X-X0TTA6BL4-Install-Command-Executed-Claim-Allowed"]
        == "false"
    )
    assert (
        response.headers["X-X0TTA6BL4-Node-Dataplane-Join-Claim-Allowed"]
        == "false"
    )
    response_json = response.json()
    assert response_json["provisioning_setup_claim_gate"][
        "local_pending_node_db_write_claim_allowed"
    ] is True
    assert response_json["provisioning_setup_claim_gate"][
        "pqc_negotiation_claim_allowed"
    ] is False
    assert response_json["cross_plane_claim_gate"]["allowed"] is False
    assert db.commits == 1
    assert events[-1].data["status"] == "created"
    assert "mesh-private" not in str(events[-1].data)
