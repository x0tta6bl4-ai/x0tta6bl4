from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/05-operations/REAL_READINESS_GATE.md"


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_real_readiness_gate_safe_actuator_counts_match_verifiers():
    text = _doc_text()

    assert "parse-error-free" in text
    assert "`21/21`" in text
    assert "`63/63`" in text
    assert "`20 EventBus + 5 result" in text
    assert "result-metadata` local cases" in text

    stale_markers = (
        "`14/14`",
        "`13/13`",
        "still incremental",
    )
    for marker in stale_markers:
        assert marker not in text


def test_real_readiness_gate_names_current_runtime_retention_surfaces():
    text = _doc_text()
    compact_text = " ".join(text.split())

    required_surfaces = (
        "SPIRE",
        "TokenBridge",
        "DAO executor release-script",
        "DAO proposal Helm upgrade",
        "DAO governance dispatch",
        "GovernanceContract chain-write",
        "Ghost L3",
        "eBPF",
        "MaaS governance",
        "PQC rotator",
        "MPTCP",
        "IntegrationSpine",
        "MeshActionEnforcer",
        "core MAPE-K aggressive healing",
        "self-healing MAPE-K",
        "PBFT",
        "Swarm MAPE-K",
        "canary deployment",
        "multi-cloud deployment",
    )
    for surface in required_surfaces:
        assert surface in compact_text


def test_real_readiness_gate_followup_lists_maas_heal_api_probe_verifier():
    text = _doc_text()

    assert "verify_maas_heal_api_post_action_dataplane_probe.py" in text
    assert "verify_maas_autonomous_mesh_runtime_smoke.py" in text
    assert "MaaS autonomous mesh runtime smoke is readiness-gated" in text
    assert "--require-ready" in text
    assert "traffic/customer/external/SLO/production claims false" in text


def test_real_readiness_gate_lists_private_target_blocked_preflight():
    text = _doc_text()

    assert "private-target operator-run verifier has a readiness-gated blocked" in text
    assert "verify_dataplane_delivery_private_target_operator_run.py" in text
    assert "--target-host 10.0.0.5 --require-retained --json" in text
    assert "without `--allow-private-target-probe`" in text


def test_real_readiness_gate_lists_integration_spine_code_wiring_gate():
    text = _doc_text()

    assert "IntegrationSpine code wiring is command-gated" in text
    assert "src/integration/code_wiring.py" in text
    assert "identity -> policy -> SafeActuator -> EventBus ->" in text
    assert "retain SafeActuator evidence metadata" in text
    assert "still report `NOT_COMPLETE`" in text


def test_real_readiness_gate_lists_ghost_pulse_current_runtime_command_gate():
    text = _doc_text()

    assert "Ghost Pulse proof gate is command-gated in no-interface mode" in text
    assert "verify_ghost_pulse_proof_gate.py --json" in text
    assert "`current_runtime_attached` false" in text
    assert "`GHOST_PULSE_RUNTIME_INTERFACE` is" in text


def test_real_readiness_gate_lists_settlement_finality_cross_plane_gate():
    text = _doc_text()
    compact_text = " ".join(text.split())

    assert "Settlement finality has its own command-gated cross-plane check" in text
    assert "run_cross_plane_proof_gate.py --claim settlement_finality" in text
    assert "retained external settlement evidence" in text
    assert "matching live RPC proof" in compact_text


def test_real_readiness_gate_lists_traffic_cross_plane_gates():
    text = _doc_text()
    compact_text = " ".join(text.split())

    assert "Traffic delivery and customer traffic have their own" in text
    assert "run_cross_plane_proof_gate.py --claim traffic_delivery" in text
    assert "run_cross_plane_proof_gate.py --claim customer_traffic" in text
    assert "fresh redacted EventBus proof" in compact_text
    assert "selected EventBus event" in compact_text
    assert "matching artifact evidence" in compact_text
