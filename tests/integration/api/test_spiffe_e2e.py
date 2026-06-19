"""End-to-end test: Go agent JWT-SVID → Python API heartbeat verification.

Tests the full SPIFFE integration flow:
1. Node registration → gets runtime credential
2. Node binds JWT-SVID identity
3. Node sends heartbeat with JWT-SVID → API verifies and accepts
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.maas.nodes.admission import (
    verified_node_runtime_identity_from_jwt_svid,
    jwt_svid_verifier_enabled,
)
from src.database import Base, MeshNode, MeshInstance, User


# --- Test fixtures ---

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def ec_keypair():
    """Generate an EC P-256 key pair for JWT signing."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture
def jwks_dict(ec_keypair):
    """Create a JWKS dict from the test key pair."""
    _, public_key = ec_keypair
    pub_numbers = public_key.public_numbers()
    
    # Convert to base64url
    import base64
    def b64url(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    
    x = pub_numbers.x.to_bytes(32, byteorder="big")
    y = pub_numbers.y.to_bytes(32, byteorder="big")
    
    return {
        "keys": [
            {
                "kid": "test-key-1",
                "kty": "EC",
                "alg": "ES256",
                "use": "sig",
                "crv": "P-256",
                "x": b64url(x),
                "y": b64url(y),
            }
        ]
    }


def create_jwt_svid(private_key, claims, kid="test-key-1"):
    """Create a signed JWT-SVID."""
    import time
    header = {"alg": "ES256", "kid": kid, "typ": "JWT"}
    # Ensure exp/iat use system clock (time.time()), not datetime.utcnow()
    # which can lag behind in some environments
    now = int(time.time())
    if "exp" not in claims:
        claims["exp"] = now + 3600
    if "iat" not in claims:
        claims["iat"] = now
    return jwt.encode(claims, private_key, algorithm="ES256", headers=header)


# --- Tests ---

class TestSPIFFEE2E:
    """End-to-end SPIFFE integration tests."""

    def test_node_registration_and_heartbeat_with_jwt_svid(
        self, db_session, ec_keypair, jwks_dict
    ):
        """Full flow: register → bind → heartbeat with JWT-SVID."""
        private_key, _ = ec_keypair
        node_id = "x0t-e2e-test-node"
        mesh_id = "mesh-e2e-test"
        
        # 1. Create mesh instance
        mesh = MeshInstance(
            id=mesh_id,
            name="E2E Test Mesh",
            owner_id="test-user",
            plan="pro",
            status="active",
            join_token="test-join-token-123",
        )
        db_session.add(mesh)
        db_session.commit()
        
        # 2. Register node (simulated - create directly in DB)
        credential = "x0tn_" + __import__("secrets").token_hex(32)
        credential_hash = hashlib.sha256(credential.encode()).hexdigest()
        
        node = MeshNode(
            id=node_id,
            mesh_id=mesh_id,
            device_class="edge",
            status="approved",
            runtime_credential_hash=credential_hash,
            runtime_credential_expires_at=datetime.utcnow() + timedelta(hours=24),
            runtime_identity_binding_type="verified_jwt_svid",
        )
        db_session.add(node)
        db_session.commit()
        
        # 3. Bind JWT-SVID identity
        spiffe_id = f"spiffe://x0tta6bl4.mesh/node/{node_id}"
        binding_payload = json.dumps(
            {
                "binding_type": "verified_jwt_svid",
                "spiffe_id": spiffe_id,
                "attestation_digest": "",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        binding_hash = "jwt-svid:" + hashlib.sha256(binding_payload.encode()).hexdigest()
        
        node.runtime_identity_binding_hash = binding_hash
        node.runtime_identity_bound_at = datetime.utcnow()
        db_session.commit()
        
        # 4. Create JWT-SVID
        import time
        now = int(time.time())
        claims = {
            "sub": spiffe_id,
            "aud": "x0tta6bl4-maas",
            "iss": "spire-server",
            "exp": now + 3600,
            "iat": now,
        }
        token = create_jwt_svid(private_key, claims)
        
        # 5. Verify JWT-SVID (simulating what nodes.py does)
        with patch(
            "src.api.maas.nodes.admission._jwt_svid_jwks_dict",
            return_value=jwks_dict,
        ), patch(
            "src.api.maas.nodes.admission.jwt_svid_verifier_enabled",
            return_value=True,
        ):
            headers = {"x-spiffe-jwt-svid": token}
            result = verified_node_runtime_identity_from_jwt_svid(
                headers,
                expected_node_id=node_id,
            )
        
        # 6. Assert verification succeeded
        assert result is not None
        assert result["verified"] is True
        assert result["binding_type"] == "verified_jwt_svid"
        assert result["spiffe_id"] == spiffe_id
        assert "attestation_digest" in result
        
        print(f"✓ SPIFFE E2E: node registered, JWT-SVID verified, spiffe_id={spiffe_id}")

    def test_expired_jwt_svid_rejected(self, ec_keypair, jwks_dict):
        """Expired JWT-SVID should be rejected."""
        private_key, _ = ec_keypair
        
        import time
        now = int(time.time())
        claims = {
            "sub": "spiffe://x0tta6bl4.mesh/node/test-expired",
            "aud": "x0tta6bl4-maas",
            "iss": "spire-server",
            "exp": now - 3600,  # expired 1 hour ago
            "iat": now - 7200,
        }
        token = create_jwt_svid(private_key, claims)
        
        with patch(
            "src.api.maas.nodes.admission._jwt_svid_jwks_dict",
            return_value=jwks_dict,
        ), patch(
            "src.api.maas.nodes.admission.jwt_svid_verifier_enabled",
            return_value=True,
        ):
            headers = {"x-spiffe-jwt-svid": token}
            result = verified_node_runtime_identity_from_jwt_svid(
                headers,
                expected_node_id="test-expired",
            )
        
        assert result is not None
        assert result["verified"] is False
        assert result["reason"] == "jwt_svid_expired"
        
        print("✓ SPIFFE E2E: expired JWT-SVID correctly rejected")

    def test_wrong_node_id_rejected(self, ec_keypair, jwks_dict):
        """JWT-SVID with wrong node_id should be rejected."""
        private_key, _ = ec_keypair
        
        import time
        now = int(time.time())
        claims = {
            "sub": "spiffe://x0tta6bl4.mesh/node/wrong-node-id",
            "aud": "x0tta6bl4-maas",
            "iss": "spire-server",
            "exp": now + 3600,
            "iat": now,
        }
        token = create_jwt_svid(private_key, claims)
        
        with patch(
            "src.api.maas.nodes.admission._jwt_svid_jwks_dict",
            return_value=jwks_dict,
        ), patch(
            "src.api.maas.nodes.admission.jwt_svid_verifier_enabled",
            return_value=True,
        ):
            headers = {"x-spiffe-jwt-svid": token}
            result = verified_node_runtime_identity_from_jwt_svid(
                headers,
                expected_node_id="correct-node-id",
            )
        
        assert result is not None
        assert result["verified"] is False
        assert result["reason"] == "jwt_svid_spiffe_id_node_mismatch"
        
        print("✓ SPIFFE E2E: wrong node_id correctly rejected")

    def test_no_jwt_svid_returns_none(self):
        """No JWT-SVID header should return None."""
        with patch(
            "src.api.maas.nodes.admission.jwt_svid_verifier_enabled",
            return_value=True,
        ):
            result = verified_node_runtime_identity_from_jwt_svid(
                {},
                expected_node_id="test",
            )
        assert result is None
        print("✓ SPIFFE E2E: missing JWT-SVID returns None")

    def test_verifier_disabled_returns_unverified(self):
        """When verifier is disabled, returns unverified result."""
        headers = {"x-spiffe-jwt-svid": "some-token"}
        with patch(
            "src.api.maas.nodes.admission.jwt_svid_verifier_enabled",
            return_value=False,
        ):
            result = verified_node_runtime_identity_from_jwt_svid(
                headers,
                expected_node_id="test",
            )
        assert result is not None
        assert result["verified"] is False
        assert result["reason"] == "jwt_svid_verifier_disabled"
        print("✓ SPIFFE E2E: verifier disabled correctly handled")
