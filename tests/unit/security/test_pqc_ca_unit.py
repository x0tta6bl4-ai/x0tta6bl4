"""Unit tests for src.security.pqc_ca — PQCSVID, PQCCertificateAuthority, PQCIdentityManager."""

from __future__ import annotations

import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import src.security.pqc_ca as mod


# ---------------------------------------------------------------------------
# Fake PQCNodeIdentity — replaces the real one (which calls PQMeshSecurityLibOQS)
# ---------------------------------------------------------------------------

_FAKE_SIG_HEX = "abcd" * 16  # 64 hex chars
_FAKE_SIG_ALG = "ML-DSA-65"
_FAKE_PUB_KEY = "cafe" * 16  # 64 hex chars


class _FakeSecurity:
    """Minimal stub for PQMeshSecurityLibOQS used by PQCNodeIdentity."""

    def __init__(self, node_id: str, kem_algorithm: str = "ML-KEM-768", sig_algorithm: str = "ML-DSA-65"):
        self.node_id = node_id
        self.pq_backend = SimpleNamespace(
            kem_algorithm=kem_algorithm,
            sig_algorithm=sig_algorithm,
            sig_alg=sig_algorithm,
        )
        self.sig_keypair = SimpleNamespace(algorithm=SimpleNamespace(value=sig_algorithm))

    def get_public_keys(self):
        return {
            "key_id": "key-00000001",
            "sig_algorithm": _FAKE_SIG_ALG,
            "sig_public_key": _FAKE_PUB_KEY,
            "kem_algorithm": "ML-KEM-768",
            "kem_public_key": "0011" * 16,
        }

    def sign(self, payload: bytes) -> bytes:
        return bytes.fromhex(_FAKE_SIG_HEX)

    def verify(self, payload: bytes, signature: bytes, pubkey: bytes) -> bool:
        return signature == bytes.fromhex(_FAKE_SIG_HEX)


class _FakeNodeIdentity:
    """Stub for PQCNodeIdentity as used by PQCCertificateAuthority and PQCIdentityManager."""

    _instance_counter = 0

    def __init__(self, node_id: str):
        type(self)._instance_counter += 1
        self.node_id = node_id
        self._rotated = False
        self.security = _FakeSecurity(node_id)
        self.did = f"did:mesh:pqc:{node_id}:key-0000"

    def sign_manifest(self, manifest_data: dict) -> dict:
        payload = json.dumps(manifest_data, sort_keys=True).encode()
        return {
            "manifest": manifest_data,
            "proof": {
                "type": _FAKE_SIG_ALG,
                "created": datetime.now().isoformat(),
                "verificationMethod": f"{self.did}#sig-1",
                "signatureValue": _FAKE_SIG_HEX,
            },
        }

    def verify_remote_node(self, signed_manifest: dict, remote_pubkey_hex: str) -> bool:
        try:
            sig = signed_manifest["proof"]["signatureValue"]
            return sig == _FAKE_SIG_HEX
        except Exception:
            return False

    def rotate_keys(self):
        self._rotated = True
        return self.did


@pytest.fixture(autouse=True)
def patch_pqc_node_identity(monkeypatch):
    """Replace PQCNodeIdentity in pqc_ca module with the fake for all tests in this file."""
    _FakeNodeIdentity._instance_counter = 0
    monkeypatch.setattr(mod, "PQCNodeIdentity", _FakeNodeIdentity)
    yield


# ---------------------------------------------------------------------------
# PQCSVID dataclass
# ---------------------------------------------------------------------------


class TestPQCSVID:
    def _make(self, **overrides) -> mod.PQCSVID:
        defaults = dict(
            spiffe_id="spiffe://x0tta6bl4.mesh/node/test",
            public_key_hex=_FAKE_PUB_KEY,
            algorithm=_FAKE_SIG_ALG,
            issued_at="2026-01-01T00:00:00",
            expires_at="2026-02-01T00:00:00",
            signature=_FAKE_SIG_HEX,
            issuer_did="did:mesh:pqc:ca:key-0000",
        )
        defaults.update(overrides)
        return mod.PQCSVID(**defaults)

    def test_fields_stored_correctly(self):
        svid = self._make()
        assert svid.spiffe_id == "spiffe://x0tta6bl4.mesh/node/test"
        assert svid.public_key_hex == _FAKE_PUB_KEY
        assert svid.algorithm == _FAKE_SIG_ALG
        assert svid.issued_at == "2026-01-01T00:00:00"
        assert svid.expires_at == "2026-02-01T00:00:00"
        assert svid.signature == _FAKE_SIG_HEX
        assert svid.issuer_did == "did:mesh:pqc:ca:key-0000"

    def test_is_dataclass(self):
        import dataclasses
        assert dataclasses.is_dataclass(mod.PQCSVID)

    def test_equality_by_value(self):
        a = self._make()
        b = self._make()
        assert a == b

    def test_inequality_on_different_spiffe_id(self):
        a = self._make(spiffe_id="spiffe://mesh/node/a")
        b = self._make(spiffe_id="spiffe://mesh/node/b")
        assert a != b


# ---------------------------------------------------------------------------
# PQCCertificateAuthority
# ---------------------------------------------------------------------------


class TestPQCCertificateAuthority:
    def test_init_sets_identity_and_zero_count(self):
        ca = mod.PQCCertificateAuthority("test-ca")
        assert ca.issued_count == 0
        assert isinstance(ca.identity, _FakeNodeIdentity)
        assert ca.identity.node_id == "test-ca"

    def test_init_default_node_id(self):
        ca = mod.PQCCertificateAuthority()
        assert ca.identity.node_id == "maas-root-ca"

    def test_issue_pqc_svid_returns_svid(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid(
            spiffe_id="spiffe://x0tta6bl4.mesh/node/worker-1",
            node_public_key_hex=_FAKE_PUB_KEY,
        )
        assert isinstance(svid, mod.PQCSVID)

    def test_issue_pqc_svid_spiffe_id_and_pubkey_stored(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid(
            spiffe_id="spiffe://x0tta6bl4.mesh/node/worker-1",
            node_public_key_hex=_FAKE_PUB_KEY,
        )
        assert svid.spiffe_id == "spiffe://x0tta6bl4.mesh/node/worker-1"
        assert svid.public_key_hex == _FAKE_PUB_KEY

    def test_issue_pqc_svid_issuer_did_matches_ca(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid("spiffe://mesh/node/x", _FAKE_PUB_KEY)
        assert svid.issuer_did == ca.identity.did

    def test_issue_pqc_svid_signature_from_identity(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid("spiffe://mesh/node/x", _FAKE_PUB_KEY)
        assert svid.signature == _FAKE_SIG_HEX

    def test_issue_pqc_svid_default_ttl_30_days(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        before = datetime.utcnow()
        svid = ca.issue_pqc_svid("spiffe://mesh/node/x", _FAKE_PUB_KEY)
        after = datetime.utcnow()

        issued = datetime.fromisoformat(svid.issued_at)
        expires = datetime.fromisoformat(svid.expires_at)
        delta = expires - issued

        assert 29 <= delta.days <= 30
        assert before <= issued <= after

    def test_issue_pqc_svid_custom_ttl(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid("spiffe://mesh/node/x", _FAKE_PUB_KEY, ttl_days=7)
        issued = datetime.fromisoformat(svid.issued_at)
        expires = datetime.fromisoformat(svid.expires_at)
        delta = expires - issued
        assert 6 <= delta.days <= 7

    def test_issue_pqc_svid_increments_counter(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        assert ca.issued_count == 0
        ca.issue_pqc_svid("spiffe://mesh/node/a", _FAKE_PUB_KEY)
        assert ca.issued_count == 1
        ca.issue_pqc_svid("spiffe://mesh/node/b", _FAKE_PUB_KEY)
        assert ca.issued_count == 2

    def test_issue_pqc_svid_algorithm_from_backend(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid("spiffe://mesh/node/x", _FAKE_PUB_KEY)
        # Algorithm comes from identity.security.pq_backend.sig_algorithm
        assert svid.algorithm == _FAKE_SIG_ALG

    def test_verify_pqc_svid_valid_returns_true(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid("spiffe://mesh/node/x", _FAKE_PUB_KEY)
        # Verifier uses identity.verify_remote_node which checks signature == _FAKE_SIG_HEX
        result = ca.verify_pqc_svid(svid, _FAKE_PUB_KEY)
        assert result is True

    def test_verify_pqc_svid_tampered_signature_returns_false(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid("spiffe://mesh/node/x", _FAKE_PUB_KEY)
        # Tamper with signature
        bad_svid = mod.PQCSVID(
            spiffe_id=svid.spiffe_id,
            public_key_hex=svid.public_key_hex,
            algorithm=svid.algorithm,
            issued_at=svid.issued_at,
            expires_at=svid.expires_at,
            signature="deadbeef" * 8,
            issuer_did=svid.issuer_did,
        )
        result = ca.verify_pqc_svid(bad_svid, _FAKE_PUB_KEY)
        assert result is False

    def test_verify_pqc_svid_builds_correct_claims(self):
        """verify_pqc_svid must rebuild claims dict in same order as issue_pqc_svid."""
        ca = mod.PQCCertificateAuthority("ca-node")
        svid = ca.issue_pqc_svid("spiffe://mesh/node/claims-test", _FAKE_PUB_KEY)
        # A round-trip verify should always succeed for a freshly issued SVID
        assert ca.verify_pqc_svid(svid, _FAKE_PUB_KEY) is True

    def test_multiple_issuances_independent(self):
        ca = mod.PQCCertificateAuthority("ca-node")
        svid_a = ca.issue_pqc_svid("spiffe://mesh/node/a", _FAKE_PUB_KEY)
        svid_b = ca.issue_pqc_svid("spiffe://mesh/node/b", "ff00" * 16)
        assert svid_a.spiffe_id != svid_b.spiffe_id
        assert svid_a.public_key_hex != svid_b.public_key_hex
        assert ca.issued_count == 2


# ---------------------------------------------------------------------------
# PQCIdentityManager
# ---------------------------------------------------------------------------


class TestPQCIdentityManager:
    def test_init_sets_node_id_and_identity(self):
        manager = mod.PQCIdentityManager("node-abc")
        assert manager.node_id == "node-abc"
        assert isinstance(manager.identity, _FakeNodeIdentity)
        assert manager.identity.node_id == "node-abc"

    def test_init_current_svid_is_none(self):
        manager = mod.PQCIdentityManager("node-abc")
        assert manager.current_svid is None

    def test_get_public_key_hex_returns_string(self):
        manager = mod.PQCIdentityManager("node-abc")
        pubkey = manager.get_public_key_hex()
        assert isinstance(pubkey, str)
        assert len(pubkey) > 0

    def test_get_public_key_hex_returns_sig_public_key(self):
        manager = mod.PQCIdentityManager("node-abc")
        pubkey = manager.get_public_key_hex()
        expected = manager.identity.security.get_public_keys()["sig_public_key"]
        assert pubkey == expected

    def test_rotate_identity_returns_svid(self):
        manager = mod.PQCIdentityManager("node-xyz")
        ca = mod.PQCCertificateAuthority("ca-root")
        svid = manager.rotate_identity(ca)
        assert isinstance(svid, mod.PQCSVID)

    def test_rotate_identity_sets_current_svid(self):
        manager = mod.PQCIdentityManager("node-xyz")
        ca = mod.PQCCertificateAuthority("ca-root")
        svid = manager.rotate_identity(ca)
        assert manager.current_svid is svid

    def test_rotate_identity_calls_rotate_keys_on_identity(self):
        manager = mod.PQCIdentityManager("node-xyz")
        ca = mod.PQCCertificateAuthority("ca-root")
        assert manager.identity._rotated is False
        manager.rotate_identity(ca)
        assert manager.identity._rotated is True

    def test_rotate_identity_spiffe_id_includes_node_id(self):
        manager = mod.PQCIdentityManager("special-node")
        ca = mod.PQCCertificateAuthority("ca-root")
        svid = manager.rotate_identity(ca)
        assert "special-node" in svid.spiffe_id
        assert svid.spiffe_id.startswith("spiffe://")

    def test_rotate_identity_increments_ca_issued_count(self):
        manager = mod.PQCIdentityManager("node-count")
        ca = mod.PQCCertificateAuthority("ca-root")
        assert ca.issued_count == 0
        manager.rotate_identity(ca)
        assert ca.issued_count == 1

    def test_multiple_rotate_calls_update_current_svid(self):
        manager = mod.PQCIdentityManager("node-multi")
        ca = mod.PQCCertificateAuthority("ca-root")
        svid1 = manager.rotate_identity(ca)
        svid2 = manager.rotate_identity(ca)
        # Both are valid SVIDs and current_svid is the last one returned
        assert manager.current_svid is svid2
        assert ca.issued_count == 2

    def test_rotate_identity_svid_issuer_matches_ca(self):
        manager = mod.PQCIdentityManager("node-issuer")
        ca = mod.PQCCertificateAuthority("ca-issuer-node")
        svid = manager.rotate_identity(ca)
        assert svid.issuer_did == ca.identity.did

    def test_two_managers_with_same_ca_independent(self):
        ca = mod.PQCCertificateAuthority("shared-ca")
        mgr_a = mod.PQCIdentityManager("node-a")
        mgr_b = mod.PQCIdentityManager("node-b")
        svid_a = mgr_a.rotate_identity(ca)
        svid_b = mgr_b.rotate_identity(ca)
        assert svid_a.spiffe_id != svid_b.spiffe_id
        assert ca.issued_count == 2
        assert mgr_a.current_svid is svid_a
        assert mgr_b.current_svid is svid_b
