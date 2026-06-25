"""
Chaos test: SPIRE agent crash mid-PQC key rotation.

Simulates SPIRE agent failure during _rotate_pqc_identity execution.
Verifies:
1. Rollback preserves old keys
2. Existing sessions continue to work with old keys
3. System does not enter isolation/deadlock state
"""

import asyncio
import os
import sys
import types
from datetime import datetime

import pytest

# Dev mode — no real SPIRE needed
os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

# ---------------------------------------------------------------------------
# Mock oqs to prevent liboqs segfaults (version mismatch: liboqs 0.15 /
# liboqs-python 0.14). We inject at sys.modules before any src import.
# ---------------------------------------------------------------------------
_mock_oqs = types.ModuleType("oqs")
_mock_oqs.Signature = lambda alg, secret_key=None: type("Sig", (), {
    "generate_keypair": lambda self: b"pub" + bytes(32),
    "export_secret_key": lambda self: b"sec" + bytes(32),
    "sign": lambda self, data: b"sig" + bytes(64),
    "verify": lambda self, data, sig, pub: True,
})()
_mock_oqs.KeyEncapsulation = lambda alg: type("KEM", (), {
    "generate_keypair": lambda self: b"pub" + bytes(32),
    "export_secret_key": lambda self: b"sec" + bytes(32),
    "encap_secret": lambda self, pub: (b"ct" + bytes(32), b"ss" + bytes(32)),
    "decap_secret": lambda self, ct: b"ss" + bytes(32),
})()
sys.modules["oqs"] = _mock_oqs
sys.modules["liboqs"] = _mock_oqs
# Also pre-mark the pqc adapter so it sees LIBOQS_AVAILABLE = True
from src.security.pqc.compat import PQMeshSecurityLibOQS as _PQC  # noqa: F811

# Now import our components under mock
from src.self_healing.pqc_zero_trust_healer import PQCZeroTrustExecutor
from src.self_healing.signed_command import SignedRemediationCommand, _seen_nonces


class _MockGateway:
    """PQC gateway that supports the minimal interface needed by tests."""

    our_dsa_public_key: bytes = b"pub" + bytes(16)
    our_dsa_secret_key: bytes = b"sec" + bytes(16)
    dsa = None  # Will be set by _rotate_pqc_identity
    sessions: dict = {}

    def rotate_session_keys(self, session_id: str) -> None:
        pass

    def create_session(self, session_id: str, peer_id: str = "peer-test") -> None:
        class _FakeSession:
            last_used = __import__("time").time()
            created_at = datetime.now()
            isolated = False

        self.sessions[session_id] = _FakeSession()


class _CrashLoader:
    """XDP loader that crashes mid-sync (simulates SPIRE agent loss)."""

    synced: bool = False
    strict_verification: bool = False

    def sync_with_gateway(self) -> None:
        self.synced = True
        raise RuntimeError("SPIRE agent connection lost during key rotation")

    def set_strict_verification(self, enabled: bool) -> None:
        self.strict_verification = enabled


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_executor(
    gateway: _MockGateway | None = None,
    loader: _CrashLoader | None = None,
    node_id: str = "chaos-test-node",
) -> PQCZeroTrustExecutor:
    _seen_nonces.clear()
    return PQCZeroTrustExecutor(
        pqc_gateway=gateway or _MockGateway(),
        pqc_loader=loader,
        node_id=node_id,
    )


@pytest.fixture(autouse=True)
def _clear_nonces():
    _seen_nonces.clear()
    yield
    _seen_nonces.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_spire_crash_mid_rotation_preserves_old_keys():
    """SPIRE crash mid-rotation: old keys survive, sessions not isolated."""
    gateway = _MockGateway()
    loader = _CrashLoader()
    executor = _make_executor(gateway, loader)

    # Capture old keys before rotation
    old_dsa_pub = gateway.our_dsa_public_key
    old_dsa_sec = gateway.our_dsa_secret_key

    # Trigger identity rotation — should fail mid-way
    result = await executor._rotate_pqc_identity()

    assert result["success"] is False, (
        f"Rotation should fail when SPIRE crashes, got: {result}"
    )
    assert "error" in result, "Result must contain error details"
    assert result.get("rolled_back") is True, (
        "Rollback flag must be set on failed rotation"
    )

    # Verify old keys are preserved (rollback)
    assert gateway.our_dsa_public_key == old_dsa_pub, (
        "Old DSA public key should be preserved after failed rotation"
    )
    assert gateway.our_dsa_secret_key == old_dsa_sec, (
        "Old DSA secret key should be preserved after failed rotation"
    )

    # Signing key must also survive rollback
    assert executor._signing_key is not None
    assert executor._verification_key == executor._signing_key

    # Signed commands must still work after rollback
    from src.self_healing.signed_command import _seen_nonces
    _seen_nonces.clear()
    signed = executor._sign_action("increase monitoring")
    result2 = await executor._execute_action(signed)
    assert result2["success"] is True, (
        f"Signed commands must work after rollback, got: {result2}"
    )

    # Existing sessions still work
    gateway.create_session("session-survivor-1")
    assert "session-survivor-1" in gateway.sessions
    assert not gateway.sessions["session-survivor-1"].isolated, (
        "Session must not be isolated after failed rotation"
    )

    # Emergency mode NOT activated by rotation failure
    assert not executor._emergency_mode_active, (
        "Emergency mode must not activate on rotation failure"
    )


@pytest.mark.asyncio
async def test_spire_crash_does_not_isolate_sessions():
    """System must not isolate sessions when SPIRE agent is unavailable."""
    gateway = _MockGateway()
    loader = _CrashLoader()
    executor = _make_executor(gateway, loader)

    for i in range(3):
        gateway.create_session(f"active-session-{i}")

    await executor._rotate_pqc_identity()

    for i in range(3):
        sid = f"active-session-{i}"
        assert sid in gateway.sessions, f"Session {sid} must survive failed rotation"
        assert not gateway.sessions[sid].isolated, (
            f"Session {sid} must not be isolated after SPIRE crash"
        )


@pytest.mark.asyncio
async def test_rotate_expired_sessions_works_without_spire():
    """Session-level rotation must work even if SPIRE is down."""
    gateway = _MockGateway()
    executor = _make_executor(gateway, loader=None)

    gateway.create_session("expired-1")
    gateway.create_session("expired-2")
    gateway.create_session("fresh-1")

    import time

    for sid in ["expired-1", "expired-2"]:
        gateway.sessions[sid].last_used = time.time() - 7200

    result = await executor._rotate_expired_sessions()
    assert result["success"] is True, (
        f"Session rotation should work without SPIRE, got: {result}"
    )


@pytest.mark.asyncio
async def test_signed_command_rejects_forged_actions():
    """SignedRemediationCommand must reject actions signed with wrong key."""
    _seen_nonces.clear()
    gateway = _MockGateway()
    executor = _make_executor(gateway)

    forged_cmd = SignedRemediationCommand.sign(
        "rotate all pqc keys",
        signing_key=b"forged_key_material_" + b"\x00" * 16,
        signing_key_id="attacker-key",
    )

    result = await executor._execute_action(forged_cmd)
    assert result["success"] is False, "Forged signed command must be rejected"
    err = result.get("error", "").lower()
    assert "signature" in err or "verification" in err, (
        f"Error must mention signature/verification, got: {result.get('error', '')}"
    )


@pytest.mark.asyncio
async def test_signed_command_round_trip_succeeds():
    """Valid SignedCommand round-trip must execute successfully."""
    _seen_nonces.clear()
    gateway = _MockGateway()
    executor = _make_executor(gateway)

    signed_cmd = executor._sign_action("clean up expired sessions")
    result = await executor._execute_action(signed_cmd)
    assert result["success"] is True, (
        f"Valid signed command must execute, got: {result}"
    )


@pytest.mark.asyncio
async def test_emergency_mode_not_activated_on_rotation_failure():
    """Emergency mode must NOT be triggered by a failed identity rotation."""
    gateway = _MockGateway()
    loader = _CrashLoader()
    executor = _make_executor(gateway, loader)

    assert not executor._emergency_mode_active

    await executor._rotate_pqc_identity()
    assert not executor._emergency_mode_active, (
        "Emergency mode must not activate on rotation failure — "
        "that would cascade a key rotation issue into a network isolation event"
    )


@pytest.mark.asyncio
async def test_emergency_mode_enable_disable():
    """Emergency mode can be toggled on and off."""
    gateway = _MockGateway()
    executor = _make_executor(gateway)

    res_on = await executor._enable_emergency_mode()
    assert res_on["success"]
    assert executor._emergency_mode_active

    res_off = await executor._disable_emergency_mode()
    assert res_off["success"]
    assert not executor._emergency_mode_active
