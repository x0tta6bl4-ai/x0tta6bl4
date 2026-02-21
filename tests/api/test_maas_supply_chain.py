"""
Integration tests for MaaS Supply Chain Security:
- DB-backed SBOM registry
- Per-node binary attestation
- Mesh attestation report
"""

import os
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, get_db, User, SBOMEntry, NodeBinaryAttestation

_TEST_DB_PATH = f"./test_supply_{uuid.uuid4().hex}.db"
engine = create_engine(f"sqlite:///{_TEST_DB_PATH}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


@pytest.fixture(scope="module")
def admin_token(client):
    email = f"admin-sc-{uuid.uuid4().hex}@test.com"
    r = client.post("/api/v1/maas/auth/register", json={"email": email, "password": "password123"})
    token = r.json()["access_token"]
    db = TestingSessionLocal()
    u = db.query(User).filter(User.api_key == token).first()
    u.role = "admin"
    db.commit()
    db.close()
    return token


@pytest.fixture(scope="module")
def user_token(client):
    email = f"user-sc-{uuid.uuid4().hex}@test.com"
    r = client.post("/api/v1/maas/auth/register", json={"email": email, "password": "password123"})
    return r.json()["access_token"]


_SBOM_PAYLOAD = {
    "version": f"3.5.0-test-{uuid.uuid4().hex[:4]}",
    "format": "CycloneDX-JSON",
    "checksum_sha256": "sha256:deadbeef" + "0" * 54,
    "components": [
        {"name": "x0tta6bl4-agent", "version": "3.5.0", "type": "application"},
        {"name": "liboqs", "version": "0.10.1", "type": "library"},
    ],
    "attestation": {
        "type": "Sigstore-Bundle",
        "signer": "ci@x0tta6bl4.net",
        "signed_at": "2026-02-21T12:00:00Z",
    },
}


class TestSBOMRegistry:
    def test_register_sbom_as_admin(self, client, admin_token):
        r = client.post(
            "/api/v1/maas/supply-chain/register-artifact",
            headers={"X-API-Key": admin_token},
            json=_SBOM_PAYLOAD,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["version"] == _SBOM_PAYLOAD["version"]
        assert "id" in data

    def test_sbom_persisted_to_db(self, client, admin_token):
        db = TestingSessionLocal()
        row = db.query(SBOMEntry).filter(SBOMEntry.version == _SBOM_PAYLOAD["version"]).first()
        db.close()
        assert row is not None
        assert row.checksum_sha256 == _SBOM_PAYLOAD["checksum_sha256"]

    def test_get_sbom_by_version(self, client, admin_token):
        r = client.get(f"/api/v1/maas/supply-chain/sbom/{_SBOM_PAYLOAD['version']}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["version"] == _SBOM_PAYLOAD["version"]
        assert len(data["components"]) == 2

    def test_get_sbom_unknown_version_404(self, client):
        r = client.get("/api/v1/maas/supply-chain/sbom/99.99.99-nonexistent")
        assert r.status_code == 404

    def test_list_sboms(self, client, admin_token):
        r = client.get("/api/v1/maas/supply-chain/sbom")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        versions = [s["version"] for s in r.json()]
        assert _SBOM_PAYLOAD["version"] in versions

    def test_duplicate_version_rejected(self, client, admin_token):
        r = client.post(
            "/api/v1/maas/supply-chain/register-artifact",
            headers={"X-API-Key": admin_token},
            json=_SBOM_PAYLOAD,
        )
        assert r.status_code == 409

    def test_non_admin_cannot_register(self, client, user_token):
        payload = dict(_SBOM_PAYLOAD)
        payload["version"] = f"3.5.1-unauth-{uuid.uuid4().hex[:4]}"
        r = client.post(
            "/api/v1/maas/supply-chain/register-artifact",
            headers={"X-API-Key": user_token},
            json=payload,
        )
        assert r.status_code == 403


class TestBinaryAttestation:
    def test_verify_matching_checksum(self, client, admin_token):
        r = client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": "nd-abc001",
                "mesh_id": "mesh-test",
                "agent_version": _SBOM_PAYLOAD["version"],
                "checksum_sha256": _SBOM_PAYLOAD["checksum_sha256"],
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "verified"
        assert data["integrity"] == "valid"
        assert data["pqc_compliant"] is True

    def test_verify_mismatched_checksum(self, client):
        r = client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": "nd-abc002",
                "mesh_id": "mesh-test",
                "agent_version": _SBOM_PAYLOAD["version"],
                "checksum_sha256": "sha256:badhash" + "f" * 57,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "mismatch"
        assert data["integrity"] == "compromised"
        assert data["pqc_compliant"] is False

    def test_verify_unknown_version(self, client):
        r = client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": "nd-abc003",
                "agent_version": "0.0.0-unknown",
                "checksum_sha256": "sha256:anything",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "unknown_version"

    def test_attestation_persisted_to_db(self, client):
        node_id = f"nd-persist-{uuid.uuid4().hex[:6]}"
        client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": node_id,
                "mesh_id": "mesh-test",
                "agent_version": _SBOM_PAYLOAD["version"],
                "checksum_sha256": _SBOM_PAYLOAD["checksum_sha256"],
            },
        )
        db = TestingSessionLocal()
        row = db.query(NodeBinaryAttestation).filter(
            NodeBinaryAttestation.node_id == node_id
        ).first()
        db.close()
        assert row is not None
        assert row.status == "verified"

    def test_attestation_upsert(self, client):
        """Re-verifying same node should update, not duplicate."""
        node_id = f"nd-upsert-{uuid.uuid4().hex[:6]}"

        # First: verified
        client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": node_id,
                "agent_version": _SBOM_PAYLOAD["version"],
                "checksum_sha256": _SBOM_PAYLOAD["checksum_sha256"],
            },
        )
        # Second: mismatch (binary tampered)
        client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": node_id,
                "agent_version": _SBOM_PAYLOAD["version"],
                "checksum_sha256": "sha256:tampered" + "0" * 55,
            },
        )

        db = TestingSessionLocal()
        rows = db.query(NodeBinaryAttestation).filter(
            NodeBinaryAttestation.node_id == node_id
        ).all()
        db.close()
        assert len(rows) == 1  # Upserted, not duplicated
        assert rows[0].status == "mismatch"

    def test_get_node_attestations(self, client, user_token):
        node_id = f"nd-hist-{uuid.uuid4().hex[:6]}"
        client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": node_id,
                "agent_version": _SBOM_PAYLOAD["version"],
                "checksum_sha256": _SBOM_PAYLOAD["checksum_sha256"],
            },
        )
        r = client.get(
            f"/api/v1/maas/supply-chain/attestations/{node_id}",
            headers={"X-API-Key": user_token},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["node_id"] == node_id
        assert len(data["attestations"]) >= 1


class TestMeshAttestationReport:
    def test_clean_mesh_report(self, client, user_token):
        mesh_id = f"mesh-clean-{uuid.uuid4().hex[:6]}"

        # Register 3 verified nodes
        for i in range(3):
            client.post(
                "/api/v1/maas/supply-chain/verify-binary",
                json={
                    "node_id": f"nd-clean-{i}",
                    "mesh_id": mesh_id,
                    "agent_version": _SBOM_PAYLOAD["version"],
                    "checksum_sha256": _SBOM_PAYLOAD["checksum_sha256"],
                },
            )

        r = client.get(
            f"/api/v1/maas/supply-chain/mesh-attestation-report/{mesh_id}",
            headers={"X-API-Key": user_token},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["integrity"] == "clean"
        assert data["summary"]["verified"] == 3
        assert data["summary"]["mismatch"] == 0
        assert data["compromised_nodes"] == []

    def test_compromised_mesh_report(self, client, user_token):
        mesh_id = f"mesh-dirty-{uuid.uuid4().hex[:6]}"

        # 2 verified, 1 mismatch
        for i in range(2):
            client.post(
                "/api/v1/maas/supply-chain/verify-binary",
                json={
                    "node_id": f"nd-dirty-ok-{i}",
                    "mesh_id": mesh_id,
                    "agent_version": _SBOM_PAYLOAD["version"],
                    "checksum_sha256": _SBOM_PAYLOAD["checksum_sha256"],
                },
            )
        bad_node = f"nd-dirty-bad-{uuid.uuid4().hex[:4]}"
        client.post(
            "/api/v1/maas/supply-chain/verify-binary",
            json={
                "node_id": bad_node,
                "mesh_id": mesh_id,
                "agent_version": _SBOM_PAYLOAD["version"],
                "checksum_sha256": "sha256:tampered" + "x" * 55,
            },
        )

        r = client.get(
            f"/api/v1/maas/supply-chain/mesh-attestation-report/{mesh_id}",
            headers={"X-API-Key": user_token},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["integrity"] == "compromised"
        assert bad_node in data["compromised_nodes"]
        assert data["summary"]["mismatch"] == 1
