from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.security.ebpf_pqc_gateway import EBPFPQCGateway, PQCSession


def _gateway_no_init():
    gw = object.__new__(EBPFPQCGateway)
    gw.sessions = {}
    return gw


def test_verify_signature_returns_false_on_exception():
    gw = _gateway_no_init()
    gw.dsa = SimpleNamespace(
        verify=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    assert gw.verify_signature(b"msg", b"sig", b"pk") is False


def test_initiate_key_exchange_requires_peer_kem_public_key():
    gw = _gateway_no_init()

    try:
        gw.initiate_key_exchange("peer-1", b"")
    except ValueError as exc:
        assert "peer_kem_public_key is required" in str(exc)
    else:
        raise AssertionError("initiate_key_exchange accepted an empty peer key")


def test_initiate_key_exchange_encapsulates_to_peer_kem_public_key():
    gw = _gateway_no_init()
    peer_kem_public_key = b"peer-kem-public"
    shared_secret = b"s" * 32
    gw.kem = MagicMock()
    gw.kem.encap_secret.return_value = (b"ciphertext", shared_secret)
    gw.our_kem_public_key = b"our-kem-public"
    gw.our_dsa_public_key = b"our-dsa-public"
    gw.our_dsa_secret_key = b"our-dsa-secret"
    gw._derive_aes_key = MagicMock(return_value=b"a" * 32)
    gw._derive_mac_key = MagicMock(return_value=b"m" * 16)

    with patch("src.security.ebpf_pqc_gateway.Signature") as signature_cls:
        signature_cls.return_value.sign.return_value = b"signature"
        session_id, ciphertext, signature = gw.initiate_key_exchange(
            "peer-1",
            peer_kem_public_key,
        )

    gw.kem.encap_secret.assert_called_once_with(peer_kem_public_key)
    assert ciphertext == b"ciphertext"
    assert signature == b"signature"
    assert gw.sessions[session_id].peer_kem_public_key == peer_kem_public_key


def test_get_ebpf_map_data_only_verified_sessions():
    gw = _gateway_no_init()

    verified = PQCSession(
        session_id="a" * 32,
        peer_id="peer-1",
        kem_public_key=b"",
        dsa_public_key=b"",
        mac_key=b"0" * 16,
        verified=True,
        created_at=1.0,
        last_used=2.0,
    )
    unverified = PQCSession(
        session_id="b" * 32,
        peer_id="peer-2",
        kem_public_key=b"",
        dsa_public_key=b"",
        mac_key=b"1" * 16,
        verified=False,
        created_at=1.0,
        last_used=2.0,
    )
    gw.sessions[verified.session_id] = verified
    gw.sessions[unverified.session_id] = unverified

    data = gw.get_ebpf_map_data()
    assert len(data) == 1
    only_value = next(iter(data.values()))
    assert only_value["verified"] == 1
    assert only_value["packet_counter"] == 0


def test_rotate_session_keys_resets_packet_counter():
    gw = _gateway_no_init()
    session = PQCSession(
        session_id="c" * 32,
        peer_id="peer-3",
        kem_public_key=b"",
        dsa_public_key=b"",
        shared_secret=b"x" * 32,
        aes_key=b"a" * 32,
        mac_key=b"m" * 16,
        verified=True,
        packet_counter=99,
        created_at=1.0,
        last_used=1.0,
    )
    gw.sessions[session.session_id] = session

    old_aes = session.aes_key
    old_mac = session.mac_key
    assert gw.rotate_session_keys(session.session_id) is True
    assert session.packet_counter == 0
    assert session.aes_key != old_aes
    assert session.mac_key != old_mac
