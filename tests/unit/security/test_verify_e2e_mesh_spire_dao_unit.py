"""Unit test for E2E Mesh + SPIRE mTLS + PQC + DAO Verification Harness."""

from scripts.ops.verify_e2e_mesh_spire_dao import main


def test_verify_e2e_mesh_spire_dao_main():
    exit_code = main()
    assert exit_code == 0
