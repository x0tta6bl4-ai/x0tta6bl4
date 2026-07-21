"""Unit tests for automated PQC SVID Rotator."""

from __future__ import annotations

import pytest
from src.security.pqc_svid_rotator import PQCSVIDRotator


def test_pqc_svid_rotator_initial_rotation():
    rotator = PQCSVIDRotator(spiffe_id="spiffe://x0tta6bl4.mesh/node/node-1", validity_seconds=60)
    rotated, bundle = rotator.check_and_rotate(force=True)

    assert rotated is True
    assert bundle.spiffe_id == "spiffe://x0tta6bl4.mesh/node/node-1"
    assert bundle.pqc_algorithm == "ML-DSA-65"
    assert bundle.rotation_count == 1
    assert len(bundle.public_key_hex) > 0


def test_pqc_svid_rotator_no_rotation_if_valid():
    rotator = PQCSVIDRotator(spiffe_id="spiffe://x0tta6bl4.mesh/node/node-1", validity_seconds=3600)
    rotator.rotate_identity_now()

    rotated, bundle = rotator.check_and_rotate(force=False)
    assert rotated is False
    assert bundle.rotation_count == 1
