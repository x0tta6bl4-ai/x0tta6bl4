"""
P1 eBPF <-> PQC-TLS integration tests.

Coverage goals:
- RateLimiterManager syncs peer session keys from /mesh/kem/session state.
- QuarantineManager triggers quarantine after repeated failed PQC verification.
- E2E flow: mocked KEM handshake -> eBPF session map write -> Prometheus counter.
"""

from unittest.mock import MagicMock, patch


def _build_mock_gateway():
    """Construct EBPFPQCGateway without running __init__/liboqs setup."""
    from src.security.ebpf_pqc_gateway import EBPFPQCGateway

    gw = object.__new__(EBPFPQCGateway)
    gw.sessions = {}
    gw.kem = MagicMock()
    shared_secret = b"s" * 32
    ciphertext = b"ct" * 100
    gw.kem.encap_secret.return_value = (ciphertext, shared_secret)
    gw.kem.decap_secret.return_value = shared_secret
    gw.dsa = MagicMock()
    gw.dsa.verify.return_value = True

    gw.our_kem_public_key = b"p" * 64
    gw.our_kem_secret_key = b"k" * 64
    gw.our_dsa_public_key = b"d" * 64
    gw.our_dsa_secret_key = b"z" * 64
    gw._derive_aes_key = MagicMock(return_value=b"a" * 32)
    gw._derive_mac_key = MagicMock(return_value=b"m" * 16)
    return gw


def _make_software_rate_limiter_manager():
    from src.network.ebpf import rate_limiter_manager as rlm_mod

    with patch.object(rlm_mod, "BCC_AVAILABLE", False):
        return rlm_mod.RateLimiterManager(interface="test0")


def _make_software_quarantine_manager(threshold: int = 2):
    from src.network.ebpf import quarantine_manager as qm_mod

    with patch.object(qm_mod, "BCC_AVAILABLE", False):
        return qm_mod.QuarantineManager(interface="lo", failure_threshold=threshold)


class TestRateLimiterPeerSessionSync:
    def test_sync_accepts_bytes_and_hex(self):
        mgr = _make_software_rate_limiter_manager()
        synced = mgr.sync_peer_session_keys(
            {
                "peer-a": b"a" * 32,
                "peer-b": "0x" + ("bb" * 32),
                "peer-c": "not-hex",
            }
        )
        assert synced == 2
        assert mgr.has_peer_session_key("peer-a") is True
        assert mgr.has_peer_session_key("peer-b") is True
        assert mgr.has_peer_session_key("peer-c") is False

    def test_require_pqc_session_key_enforced(self):
        mgr = _make_software_rate_limiter_manager()
        mgr.set_limit(0)
        mgr.sync_peer_session_keys({"peer-ok": b"x" * 32})

        assert mgr.check_rate_limit(
            packet_size=128,
            peer_id="peer-ok",
            require_pqc_session=True,
        )
        assert not mgr.check_rate_limit(
            packet_size=128,
            peer_id="peer-missing",
            require_pqc_session=True,
        )
        assert not mgr.check_rate_limit(
            packet_size=128,
            peer_id=None,
            require_pqc_session=True,
        )


class TestQuarantineManagerPQCFailureTrigger:
    def test_quarantine_after_threshold(self):
        qm = _make_software_quarantine_manager(threshold=2)
        ip = "10.1.1.9"

        assert not qm.record_pqc_verification_result(
            peer_id="peer-1",
            ip_address=ip,
            verified=False,
            reason="invalid_signature",
        )
        assert qm.record_pqc_verification_result(
            peer_id="peer-1",
            ip_address=ip,
            verified=False,
            reason="invalid_signature",
        )
        assert qm.is_blocked(ip) is True
        assert qm.is_using_software_fallback is True

    def test_success_resets_failure_counter(self):
        qm = _make_software_quarantine_manager(threshold=2)
        ip = "10.1.1.10"

        assert not qm.record_pqc_verification_result("peer-2", ip, verified=False)
        assert not qm.record_pqc_verification_result("peer-2", ip, verified=True)
        assert not qm.record_pqc_verification_result("peer-2", ip, verified=False)
        assert qm.is_blocked(ip) is False


class TestPQCHandshakeToMapWriteMetricsE2E:
    def test_kem_handshake_to_map_write_and_counter(self):
        gateway = _build_mock_gateway()

        # 1) KEM handshake (mocked oqs)
        with patch("src.security.ebpf_pqc_gateway.Signature") as sig_ctor:
            sig_ctor.return_value.sign.return_value = b"sig" * 20
            session_id, ciphertext, signature = gateway.initiate_key_exchange("peer-1")
        assert gateway.complete_key_exchange(
            session_id, ciphertext, signature, b"peer-pub"
        )

        # 2) eBPF map data emitted from verified session
        ebpf_map_data = gateway.get_ebpf_map_data()
        assert len(ebpf_map_data) == 1

        # 3) map write + Prometheus counter increment
        from src.network.ebpf import pqc_xdp_loader as loader_mod

        loader = object.__new__(loader_mod.PQCXDPLoader)
        loader.pqc_sessions_map = MagicMock()
        loader.pqc_sessions_map.keys.return_value = []

        mock_counter = MagicMock()
        with patch.object(
            loader_mod, "PQC_EBPF_SESSION_MAP_WRITES_TOTAL", mock_counter
        ):
            loader.update_pqc_sessions(ebpf_map_data)

        loader.pqc_sessions_map.__setitem__.assert_called_once()
        mock_counter.inc.assert_called_once_with(1)

        # 4) Session key handoff to rate limiter manager
        mgr = _make_software_rate_limiter_manager()
        synced = mgr.sync_peer_session_keys({"peer-1": gateway.sessions[session_id].aes_key})
        assert synced == 1
        assert mgr.has_peer_session_key("peer-1")
        assert mgr.check_rate_limit(
            packet_size=64, peer_id="peer-1", require_pqc_session=True
        )
