from types import SimpleNamespace

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
