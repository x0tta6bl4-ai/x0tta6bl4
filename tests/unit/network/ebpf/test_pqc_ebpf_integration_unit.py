"""
P1 Unit Tests: eBPF <-> PQC-TLS verification integration.

Tests the full chain:
  KEM handshake (EBPFPQCGateway) -> get_ebpf_map_data() -> eBPF session map format
  -> PQCXDPLoader.update_pqc_sessions() -> RateLimiterManager software fallback

All tests run without root or BCC — uses mocks and object.__new__() bypass.
"""
import hashlib
import os
import struct
import time
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_SHARED_SECRET = b"x" * 32
MOCK_CIPHERTEXT = b"ct" * 100
MOCK_PUB_KEY = b"pk" * 50
MOCK_SEC_KEY = b"sk" * 100
MOCK_SIGNATURE = b"sig" * 20


def _make_verified_session(session_id: str, peer_id: str = "peer-1"):
    """Return a fully-populated, verified PQCSession (no oqs needed)."""
    from src.security.ebpf_pqc_gateway import PQCSession

    s = PQCSession(
        session_id=session_id,
        peer_id=peer_id,
        kem_public_key=b"pub",
        dsa_public_key=b"dsa_pub",
        shared_secret=b"x" * 32,
        aes_key=os.urandom(32),
        mac_key=os.urandom(16),
        last_seq=42,
        window_bitmap=0xFF,
        packet_counter=100,
        verified=True,
    )
    s.last_used = time.time()
    return s


def _gateway_with_sessions(sessions: dict):
    """Create EBPFPQCGateway bypassing __init__ — inject sessions directly."""
    from src.security.ebpf_pqc_gateway import EBPFPQCGateway

    gw = object.__new__(EBPFPQCGateway)
    gw.sessions = sessions
    return gw


@pytest.fixture
def mock_pqc_gateway():
    """
    EBPFPQCGateway with mocked internals — bypasses __init__ entirely.

    Uses object.__new__() to avoid oqs/liboqs calls. HKDF derivation methods
    are mocked at the instance level so tests are hermetic and deterministic.
    A fixed aes_key (32 bytes) is shared across _derive_aes_key calls so that
    encrypt/decrypt roundtrips work without real HKDF.
    """
    from src.security.ebpf_pqc_gateway import EBPFPQCGateway

    gw = object.__new__(EBPFPQCGateway)
    gw.sessions = {}

    # Mock oqs KEM/DSA objects on the gateway instance
    gw.kem = MagicMock()
    gw.kem.encap_secret.return_value = (MOCK_CIPHERTEXT, MOCK_SHARED_SECRET)
    gw.kem.decap_secret.return_value = MOCK_SHARED_SECRET

    gw.dsa = MagicMock()
    gw.dsa.verify.return_value = True

    # Synthetic keypairs (raw bytes, not real PQC keys)
    gw.our_kem_public_key = MOCK_PUB_KEY
    gw.our_kem_secret_key = MOCK_SEC_KEY
    gw.our_dsa_public_key = MOCK_PUB_KEY
    gw.our_dsa_secret_key = MOCK_SEC_KEY

    # Fixed derived keys so encrypt/decrypt roundtrips are deterministic
    _aes_key = os.urandom(32)
    _mac_key = os.urandom(16)
    gw._derive_aes_key = MagicMock(return_value=_aes_key)
    gw._derive_mac_key = MagicMock(return_value=_mac_key)

    # Patch module-level Signature constructor used inside initiate_key_exchange
    with patch("src.security.ebpf_pqc_gateway.Signature") as mock_sig_cls:
        mock_sig_cls.return_value.sign.return_value = MOCK_SIGNATURE
        mock_sig_cls.return_value.verify.return_value = True
        yield gw


# ============================================================================
# A. SoftwareRateLimiter — token-bucket logic
# ============================================================================


class TestSoftwareRateLimiter:
    def _make(self):
        from src.network.ebpf.rate_limiter_manager import SoftwareRateLimiter

        return SoftwareRateLimiter()

    def test_unlimited_allows_any_packet(self):
        rl = self._make()
        for _ in range(500):
            assert rl.check_and_consume(1500) is True

    def test_set_limit_stores_rate(self):
        rl = self._make()
        rl.set_limit(8192)
        assert rl.get_stats()["bytes_per_sec"] == 8192

    def test_unlimited_zero_is_default(self):
        rl = self._make()
        assert rl._bytes_per_sec == 0

    def test_apply_soft_lock_sets_8192_bps(self):
        rl = self._make()
        rl.apply_soft_lock()
        assert rl.get_stats()["bytes_per_sec"] == 8192  # 64 Kbps

    def test_drops_when_bucket_empty(self):
        rl = self._make()
        rl.set_limit(100)
        rl.check_and_consume(100)  # drain the bucket
        assert rl.check_and_consume(1) is False

    def test_stats_tracks_totals(self):
        rl = self._make()
        rl.set_limit(100)
        rl.check_and_consume(100)  # allowed
        rl.check_and_consume(1000)  # dropped
        s = rl.get_stats()
        assert s["total_packets"] == 2
        assert s["dropped_packets"] == 1
        assert s["drop_rate"] == pytest.approx(0.5)

    def test_stats_mode_is_software(self):
        rl = self._make()
        assert rl.get_stats()["mode"] == "software"

    def test_tokens_cap_at_rate(self):
        rl = self._make()
        rl.set_limit(1000)
        # Manually set tokens above cap
        rl._tokens = 5000.0
        rl._last_time = time.time()
        rl.check_and_consume(1)
        # After refill step, tokens should be capped at 1000
        assert rl._tokens <= 1000


# ============================================================================
# B. RateLimiterManager — software fallback path
# ============================================================================


class TestRateLimiterManagerSoftware:
    @pytest.fixture
    def manager(self):
        from src.network.ebpf import rate_limiter_manager

        with patch.object(rate_limiter_manager, "BCC_AVAILABLE", False):
            mgr = rate_limiter_manager.RateLimiterManager.__new__(
                rate_limiter_manager.RateLimiterManager
            )
            mgr.interface = "test0"
            mgr.bpf = None
            mgr._using_software_fallback = False
            mgr._software_limiter = None
            mgr._init_eBPF_or_fallback()
        return mgr

    def test_is_using_software_fallback(self, manager):
        assert manager.is_using_software_fallback is True

    def test_set_limit_delegates_to_software(self, manager):
        manager.set_limit(8192)
        assert manager._software_limiter.get_stats()["bytes_per_sec"] == 8192

    def test_apply_soft_lock_sets_8192(self, manager):
        manager.apply_soft_lock()
        assert manager._software_limiter.get_stats()["bytes_per_sec"] == 8192

    def test_check_rate_limit_unlimited(self, manager):
        manager.set_limit(0)
        assert manager.check_rate_limit(1500) is True

    def test_check_rate_limit_drops_when_exceeded(self, manager):
        manager.set_limit(10)
        manager._software_limiter._tokens = 0.0
        assert manager.check_rate_limit(1500) is False

    def test_get_stats_returns_software_stats(self, manager):
        stats = manager.get_stats()
        assert stats["mode"] == "software"

    def test_no_bcc_triggers_software_fallback_on_init(self):
        from src.network.ebpf import rate_limiter_manager

        with patch.object(rate_limiter_manager, "BCC_AVAILABLE", False):
            mgr = rate_limiter_manager.RateLimiterManager.__new__(
                rate_limiter_manager.RateLimiterManager
            )
            mgr.interface = "lo"
            mgr.bpf = None
            mgr._using_software_fallback = False
            mgr._software_limiter = None
            mgr._init_eBPF_or_fallback()
            assert mgr.is_using_software_fallback is True
            assert mgr._software_limiter is not None


# ============================================================================
# C. EBPFPQCGateway.get_ebpf_map_data() — format verification
# ============================================================================


class TestEBPFPQCGatewayMapData:
    """Verify the eBPF map data format matches what xdp_pqc_verify.c expects."""

    def test_empty_sessions_returns_empty(self):
        gw = _gateway_with_sessions({})
        assert gw.get_ebpf_map_data() == {}

    def test_unverified_session_excluded(self):
        from src.security.ebpf_pqc_gateway import PQCSession

        sid = "aa" * 16
        s = PQCSession(
            session_id=sid,
            peer_id="p",
            kem_public_key=b"k",
            dsa_public_key=b"d",
            mac_key=b"x" * 16,
            verified=False,
        )
        gw = _gateway_with_sessions({sid: s})
        assert gw.get_ebpf_map_data() == {}

    def test_session_without_mac_key_excluded(self):
        from src.security.ebpf_pqc_gateway import PQCSession

        sid = "bb" * 16
        s = PQCSession(
            session_id=sid,
            peer_id="p",
            kem_public_key=b"k",
            dsa_public_key=b"d",
            mac_key=None,
            verified=True,
        )
        gw = _gateway_with_sessions({sid: s})
        assert gw.get_ebpf_map_data() == {}

    def test_verified_session_appears_in_map(self):
        sid = "cc" * 16
        gw = _gateway_with_sessions({sid: _make_verified_session(sid)})
        assert len(gw.get_ebpf_map_data()) == 1

    def test_map_key_is_16_byte_binary(self):
        sid = "dd" * 16
        gw = _gateway_with_sessions({sid: _make_verified_session(sid)})
        key = next(iter(gw.get_ebpf_map_data()))
        assert isinstance(key, bytes)
        assert len(key) == 16
        assert key == bytes.fromhex(sid)

    def test_mac_key_is_list_of_16_ints(self):
        sid = "ee" * 16
        gw = _gateway_with_sessions({sid: _make_verified_session(sid)})
        entry = next(iter(gw.get_ebpf_map_data().values()))
        assert isinstance(entry["mac_key"], list)
        assert len(entry["mac_key"]) == 16
        assert all(0 <= b <= 255 for b in entry["mac_key"])

    def test_mac_key_matches_session_mac_key(self):
        sid = "ff" * 16
        session = _make_verified_session(sid)
        gw = _gateway_with_sessions({sid: session})
        entry = next(iter(gw.get_ebpf_map_data().values()))
        assert entry["mac_key"] == list(session.mac_key)

    def test_verified_flag_is_1(self):
        sid = "ab" * 16
        gw = _gateway_with_sessions({sid: _make_verified_session(sid)})
        entry = next(iter(gw.get_ebpf_map_data().values()))
        assert entry["verified"] == 1

    def test_peer_id_hash_is_u64(self):
        sid = "12" * 16
        gw = _gateway_with_sessions({sid: _make_verified_session(sid, "node-abc")})
        entry = next(iter(gw.get_ebpf_map_data().values()))
        peer_hash = entry["peer_id_hash"]
        assert isinstance(peer_hash, int)
        assert 0 <= peer_hash < 2**64

    def test_peer_id_hash_derived_from_sha256(self):
        sid = "34" * 16
        peer_id = "node-xyz"
        gw = _gateway_with_sessions({sid: _make_verified_session(sid, peer_id)})
        entry = next(iter(gw.get_ebpf_map_data().values()))
        expected = struct.unpack("<Q", hashlib.sha256(peer_id.encode()).digest()[:8])[0]
        assert entry["peer_id_hash"] == expected

    def test_last_seq_preserved(self):
        sid = "56" * 16
        session = _make_verified_session(sid)
        session.last_seq = 999
        gw = _gateway_with_sessions({sid: session})
        entry = next(iter(gw.get_ebpf_map_data().values()))
        assert entry["last_seq"] == 999

    def test_window_bitmap_preserved(self):
        sid = "78" * 16
        session = _make_verified_session(sid)
        session.window_bitmap = 0xDEADBEEF
        gw = _gateway_with_sessions({sid: session})
        entry = next(iter(gw.get_ebpf_map_data().values()))
        assert entry["window_bitmap"] == 0xDEADBEEF

    def test_packet_counter_preserved(self):
        sid = "90" * 16
        session = _make_verified_session(sid)
        session.packet_counter = 42
        gw = _gateway_with_sessions({sid: session})
        entry = next(iter(gw.get_ebpf_map_data().values()))
        assert entry["packet_counter"] == 42

    def test_multiple_verified_sessions_all_in_map(self):
        sessions = {}
        for i in range(4):
            sid = f"{i:02x}" * 16
            sessions[sid] = _make_verified_session(sid, f"peer-{i}")
        gw = _gateway_with_sessions(sessions)
        assert len(gw.get_ebpf_map_data()) == 4

    def test_mixed_verified_unverified_only_verified_exported(self):
        from src.security.ebpf_pqc_gateway import PQCSession

        sid_v = "11" * 16
        sid_u = "22" * 16
        v = _make_verified_session(sid_v)
        u = PQCSession(
            session_id=sid_u,
            peer_id="p2",
            kem_public_key=b"k",
            dsa_public_key=b"d",
            mac_key=b"x" * 16,
            verified=False,
        )
        gw = _gateway_with_sessions({sid_v: v, sid_u: u})
        data = gw.get_ebpf_map_data()
        assert len(data) == 1
        assert bytes.fromhex(sid_v) in data


# ============================================================================
# D. EBPFPQCGateway — full KEM handshake flow (mocked oqs)
# ============================================================================


class TestKEMToEBPFMapE2EFlow:
    """E2E: KEM handshake -> session verified -> appears in eBPF map."""

    def test_create_session_is_unverified(self, mock_pqc_gateway):
        s = mock_pqc_gateway.create_session("peer-1")
        assert s.verified is False
        assert s.peer_id == "peer-1"

    def test_initiate_key_exchange_returns_3tuple(self, mock_pqc_gateway):
        result = mock_pqc_gateway.initiate_key_exchange("peer-1")
        assert len(result) == 3
        sid, ct, sig = result
        assert isinstance(sid, str)
        assert isinstance(ct, bytes)
        assert isinstance(sig, bytes)

    def test_initiate_sets_aes_key_32_bytes(self, mock_pqc_gateway):
        sid, _, _ = mock_pqc_gateway.initiate_key_exchange("peer-1")
        assert len(mock_pqc_gateway.sessions[sid].aes_key) == 32

    def test_initiate_sets_mac_key_16_bytes(self, mock_pqc_gateway):
        sid, _, _ = mock_pqc_gateway.initiate_key_exchange("peer-1")
        assert len(mock_pqc_gateway.sessions[sid].mac_key) == 16

    def test_initiated_session_not_yet_in_ebpf_map(self, mock_pqc_gateway):
        mock_pqc_gateway.initiate_key_exchange("peer-1")
        assert mock_pqc_gateway.get_ebpf_map_data() == {}

    def test_complete_key_exchange_marks_verified(self, mock_pqc_gateway):
        sid, ct, sig = mock_pqc_gateway.initiate_key_exchange("peer-2")
        ok = mock_pqc_gateway.complete_key_exchange(sid, ct, sig, MOCK_PUB_KEY)
        assert ok is True
        assert mock_pqc_gateway.sessions[sid].verified is True

    def test_kem_to_ebpf_map_full_e2e(self, mock_pqc_gateway):
        """Full E2E: KEM handshake -> verified session -> eBPF map entry."""
        sid, ct, sig = mock_pqc_gateway.initiate_key_exchange("peer-3")
        mock_pqc_gateway.complete_key_exchange(sid, ct, sig, MOCK_PUB_KEY)

        data = mock_pqc_gateway.get_ebpf_map_data()
        assert len(data) == 1
        key = bytes.fromhex(sid)
        assert key in data
        entry = data[key]
        assert entry["verified"] == 1
        assert len(entry["mac_key"]) == 16
        assert isinstance(entry["peer_id_hash"], int)
        assert entry["last_seq"] >= 0

    def test_invalid_session_id_returns_false(self, mock_pqc_gateway):
        result = mock_pqc_gateway.complete_key_exchange("nonexistent", b"ct", b"sig", b"pub")
        assert result is False

    def test_encrypt_decrypt_roundtrip(self, mock_pqc_gateway):
        sid, ct, sig = mock_pqc_gateway.initiate_key_exchange("peer-4")
        mock_pqc_gateway.complete_key_exchange(sid, ct, sig, MOCK_PUB_KEY)

        plaintext = b"hello mesh node PQC"
        encrypted = mock_pqc_gateway.encrypt_payload(sid, plaintext)
        assert encrypted is not None
        decrypted = mock_pqc_gateway.decrypt_payload(sid, encrypted)
        assert decrypted == plaintext

    def test_encrypt_unverified_session_returns_none(self, mock_pqc_gateway):
        s = mock_pqc_gateway.create_session("peer-5")
        result = mock_pqc_gateway.encrypt_payload(s.session_id, b"test")
        assert result is None

    def test_cleanup_expired_sessions(self, mock_pqc_gateway):
        s = mock_pqc_gateway.create_session("peer-6")
        mock_pqc_gateway.sessions[s.session_id].created_at = time.time() - 7200
        mock_pqc_gateway.cleanup_expired_sessions()
        assert s.session_id not in mock_pqc_gateway.sessions

    def test_rotate_session_keys_resets_counters(self, mock_pqc_gateway):
        sid, ct, sig = mock_pqc_gateway.initiate_key_exchange("peer-7")
        mock_pqc_gateway.complete_key_exchange(sid, ct, sig, MOCK_PUB_KEY)
        mock_pqc_gateway.sessions[sid].last_seq = 999
        mock_pqc_gateway.sessions[sid].packet_counter = 500

        result = mock_pqc_gateway.rotate_session_keys(sid)
        assert result is True
        assert mock_pqc_gateway.sessions[sid].last_seq == 0
        assert mock_pqc_gateway.sessions[sid].packet_counter == 0

    def test_get_session_info_returns_none_for_unverified(self, mock_pqc_gateway):
        s = mock_pqc_gateway.create_session("peer-8")
        info = mock_pqc_gateway.get_session_info(s.session_id)
        assert info is None

    def test_get_session_info_returns_dict_for_verified(self, mock_pqc_gateway):
        sid, ct, sig = mock_pqc_gateway.initiate_key_exchange("peer-9")
        mock_pqc_gateway.complete_key_exchange(sid, ct, sig, MOCK_PUB_KEY)
        info = mock_pqc_gateway.get_session_info(sid)
        assert info is not None
        assert info["verified"] is True
        assert info["peer_id"] == "peer-9"


# ============================================================================
# E. PQCXDPLoader — update_pqc_sessions / sync_with_gateway (bypass __init__)
# ============================================================================


@pytest.fixture
def xdp_loader():
    """PQCXDPLoader with mocked internals — bypasses __init__ entirely."""
    from src.network.ebpf.pqc_xdp_loader import PQCXDPLoader

    loader = object.__new__(PQCXDPLoader)
    loader.interface = "test0"
    loader.bpf = None
    loader.programs_dir = MagicMock()

    mock_map = MagicMock()
    mock_map.keys.return_value = []
    loader.pqc_sessions_map = mock_map
    loader.pqc_stats_map = None

    mock_gw = MagicMock()
    mock_gw.get_ebpf_map_data.return_value = {}
    mock_gw.sessions = {}
    loader.pqc_gateway = mock_gw

    return loader


class TestPQCXDPLoaderMocked:
    def test_update_pqc_sessions_clears_existing_entries(self, xdp_loader):
        existing_key = b"\x01" * 16
        xdp_loader.pqc_sessions_map.keys.return_value = [existing_key]
        xdp_loader.update_pqc_sessions({})
        xdp_loader.pqc_sessions_map.__delitem__.assert_called_once_with(existing_key)

    def test_update_pqc_sessions_adds_new_entry(self, xdp_loader):
        key = os.urandom(16)
        info = {"mac_key": [0] * 16, "verified": 1, "peer_id_hash": 0, "last_seq": 0, "window_bitmap": 0, "timestamp": 0}
        xdp_loader.update_pqc_sessions({key: info})
        xdp_loader.pqc_sessions_map.__setitem__.assert_called_once_with(key, info)

    def test_update_pqc_sessions_no_map_is_noop(self, xdp_loader):
        xdp_loader.pqc_sessions_map = None
        xdp_loader.update_pqc_sessions({"key": "val"})  # must not raise

    def test_sync_with_gateway_calls_get_ebpf_map_data(self, xdp_loader):
        xdp_loader.sync_with_gateway()
        xdp_loader.pqc_gateway.get_ebpf_map_data.assert_called_once()

    def test_sync_with_gateway_passes_data_to_update(self, xdp_loader):
        key = os.urandom(16)
        data = {key: {"verified": 1, "mac_key": [0] * 16, "peer_id_hash": 0, "last_seq": 0, "window_bitmap": 0, "timestamp": 0}}
        xdp_loader.pqc_gateway.get_ebpf_map_data.return_value = data
        xdp_loader.pqc_sessions_map.keys.return_value = []
        xdp_loader.sync_with_gateway()
        xdp_loader.pqc_sessions_map.__setitem__.assert_called_once_with(key, data[key])

    def test_get_pqc_stats_returns_empty_when_no_stats_map(self, xdp_loader):
        xdp_loader.pqc_stats_map = None
        assert xdp_loader.get_pqc_stats() == {}

    def test_cleanup_calls_remove_xdp(self, xdp_loader):
        mock_bpf = MagicMock()
        xdp_loader.bpf = mock_bpf
        xdp_loader.cleanup()
        mock_bpf.remove_xdp.assert_called_once_with("test0", 0)

    def test_create_pqc_session_returns_session_id(self, xdp_loader):
        mock_session = MagicMock()
        mock_session.session_id = "abc123"
        xdp_loader.pqc_gateway.create_session.return_value = mock_session
        result = xdp_loader.create_pqc_session("peer-1")
        assert result == "abc123"
        xdp_loader.pqc_gateway.create_session.assert_called_once_with("peer-1")

    def test_create_pqc_session_syncs_gateway(self, xdp_loader):
        mock_session = MagicMock()
        mock_session.session_id = "xyz789"
        xdp_loader.pqc_gateway.create_session.return_value = mock_session
        xdp_loader.create_pqc_session("peer-2")
        xdp_loader.pqc_gateway.get_ebpf_map_data.assert_called()

    def test_create_pqc_session_exception_returns_none(self, xdp_loader):
        xdp_loader.pqc_gateway.create_session.side_effect = RuntimeError("oops")
        result = xdp_loader.create_pqc_session("peer-3")
        assert result is None
