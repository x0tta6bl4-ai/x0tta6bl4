"""Unit test for GNN + MAPE-K Evals Verification Harness."""

from scripts.ops.verify_gnn_mapek_harness import main


def test_verify_gnn_mapek_harness_main():
    exit_code = main()
    assert exit_code == 0
