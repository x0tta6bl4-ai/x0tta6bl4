import json
from pathlib import Path

from src.security.pqc import key_rotation


def _make_config(tmp_path: Path) -> key_rotation.KeyRotationConfig:
    return key_rotation.KeyRotationConfig(
        rotation_interval=60.0,
        backup_retention=3600.0,
        max_backups=5,
        backup_path=str(tmp_path / "backups"),
        master_key_path=str(tmp_path / "master.key"),
    )


def test_rotate_kem_creates_backup_for_old_key(monkeypatch, tmp_path):
    monkeypatch.setattr(key_rotation, "LIBOQS_AVAILABLE", True)
    manager = key_rotation.PQCKeyRotation(
        node_id="node-a",
        config=_make_config(tmp_path),
        master_key=b"a" * 32,
    )
    monkeypatch.setattr(manager, "_encrypt_key", lambda key: b"enc:" + key)

    keypairs = iter(
        [
            (b"kem-public-1", b"kem-private-1"),
            (b"kem-public-2", b"kem-private-2"),
        ]
    )
    monkeypatch.setattr(manager, "generate_kem_keypair", lambda *_: next(keypairs))

    first = manager.rotate_kem_key()
    second = manager.rotate_kem_key()

    assert first.is_active is False
    assert first.rotated_at is not None
    assert second.is_active is True
    assert manager.get_current_kem_key().key_id == second.key_id

    assert first.backup_location is not None
    backup_file = Path(first.backup_location)
    assert backup_file.exists()
    backup_data = json.loads(backup_file.read_text())
    assert backup_data["key_id"] == first.key_id
    assert backup_data["key_type"] == "kem"


def test_recover_key_returns_record_from_backup(monkeypatch, tmp_path):
    monkeypatch.setattr(key_rotation, "LIBOQS_AVAILABLE", True)
    manager = key_rotation.PQCKeyRotation(
        node_id="node-a",
        config=_make_config(tmp_path),
        master_key=b"a" * 32,
    )
    monkeypatch.setattr(manager, "_encrypt_key", lambda key: b"enc:" + key)

    keypairs = iter(
        [
            (b"sig-public-1", b"sig-private-1"),
            (b"sig-public-2", b"sig-private-2"),
        ]
    )
    monkeypatch.setattr(manager, "generate_signature_keypair", lambda *_: next(keypairs))

    first = manager.rotate_signature_key()
    manager.rotate_signature_key()

    recovered = manager.recover_key(first.key_id, "signature")
    assert recovered is not None
    assert recovered.key_id == first.key_id
    assert recovered.is_active is False
    assert recovered.backup_location is not None


def test_should_rotate_based_on_age(monkeypatch, tmp_path):
    monkeypatch.setattr(key_rotation, "LIBOQS_AVAILABLE", True)
    config = _make_config(tmp_path)
    config.rotation_interval = 1.0
    manager = key_rotation.PQCKeyRotation(
        node_id="node-a",
        config=config,
        master_key=b"a" * 32,
    )
    monkeypatch.setattr(manager, "_encrypt_key", lambda key: b"enc:" + key)

    keypairs = iter(
        [
            (b"kem-public-1", b"kem-private-1"),
            (b"sig-public-1", b"sig-private-1"),
        ]
    )
    monkeypatch.setattr(manager, "generate_kem_keypair", lambda *_: next(keypairs))
    monkeypatch.setattr(
        manager, "generate_signature_keypair", lambda *_: next(keypairs)
    )

    manager.rotate_kem_key()
    manager.rotate_signature_key()

    # Simulate keys older than rotation interval.
    manager.get_current_kem_key().created_at -= 5.0
    manager.get_current_sig_key().created_at -= 5.0

    should_rotate_kem, should_rotate_sig = manager.should_rotate()
    assert should_rotate_kem is True
    assert should_rotate_sig is True
