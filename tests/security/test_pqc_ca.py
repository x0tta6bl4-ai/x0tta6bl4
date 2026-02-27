"""Smoke tests for PQCCertificateAuthority and PQCIdentityManager."""
import pytest
from src.security.pqc_ca import PQCCertificateAuthority, PQCIdentityManager, PQCSVID


class TestPQCCertificateAuthority:
    def setup_method(self):
        self.ca = PQCCertificateAuthority(ca_node_id="test-ca")

    def test_init(self):
        assert self.ca.issued_count == 0

    def test_issue_pqc_svid_returns_svid(self):
        svid = self.ca.issue_pqc_svid(
            spiffe_id="spiffe://x0tta6bl4.mesh/test-node",
            node_public_key_hex="deadbeef",
        )
        assert isinstance(svid, PQCSVID)
        assert svid.spiffe_id == "spiffe://x0tta6bl4.mesh/test-node"
        assert svid.algorithm == "ML-DSA-65"
        assert svid.issuer_did.startswith("did:")
        assert svid.signature != ""

    def test_issued_count_increments(self):
        self.ca.issue_pqc_svid("spiffe://x0tta6bl4.mesh/n1", "aa")
        self.ca.issue_pqc_svid("spiffe://x0tta6bl4.mesh/n2", "bb")
        assert self.ca.issued_count == 2

    def test_svid_expiry_fields_present(self):
        svid = self.ca.issue_pqc_svid("spiffe://x0tta6bl4.mesh/n", "pub", ttl_days=7)
        assert svid.issued_at != ""
        assert svid.expires_at != ""


class TestPQCIdentityManager:
    def setup_method(self):
        self.ca = PQCCertificateAuthority(ca_node_id="test-ca")
        self.mgr = PQCIdentityManager("node-42")

    def test_initial_svid_is_none(self):
        assert self.mgr.current_svid is None

    def test_rotate_identity_issues_svid(self):
        svid = self.mgr.rotate_identity(self.ca)
        assert isinstance(svid, PQCSVID)
        assert "node-42" in svid.spiffe_id
        assert self.mgr.current_svid is svid

    def test_rotate_identity_twice_updates_current(self):
        self.mgr.rotate_identity(self.ca)
        svid2 = self.mgr.rotate_identity(self.ca)
        assert self.mgr.current_svid is svid2

    def test_get_public_key_hex_returns_string(self):
        key = self.mgr.get_public_key_hex()
        assert isinstance(key, str)
        assert len(key) > 0
